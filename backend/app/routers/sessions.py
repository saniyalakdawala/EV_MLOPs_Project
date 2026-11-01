"""
Sessions & Charging Lifecycle Router
Atomic transactions, Row-Level Locking (SELECT ... FOR UPDATE), and status history.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from app.database import get_db_connection
from app.models import (
    StartSessionRequest,
    EndSessionRequest,
    SessionSchema,
    StatusHistorySchema
)

router = APIRouter(prefix="/api/sessions", tags=["Charging Sessions"])

@router.post("/start", status_code=status.HTTP_201_CREATED, response_model=SessionSchema)
def start_charging_session(req: StartSessionRequest):
    """
    Transactionally starts a charging session with Row-Level Locking:
    1. Begins transaction
    2. SELECT ... FOR UPDATE on target port to prevent race conditions
    3. Verifies port status is 'AVAILABLE' (returns 409 Conflict if not)
    4. Transitions port status to 'IN_USE'
    5. Inserts active session record
    6. Logs audit entry in station_status_history
    7. Commits transaction
    """
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Acquire exclusive row lock on the selected port
                cur.execute("""
                SELECT port_id, station_id, status 
                FROM charging_ports 
                WHERE port_id = %s 
                FOR UPDATE;
                """, (req.port_id,))
                port = cur.fetchone()

                if not port:
                    raise HTTPException(status_code=404, detail=f"Port with ID {req.port_id} does not exist")

                # 2. Check Availability
                if port['status'] != 'AVAILABLE':
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Conflict: Port {req.port_id} is currently '{port['status']}' and cannot be booked."
                    )

                # 3. Transition Port to IN_USE
                cur.execute("""
                UPDATE charging_ports 
                SET status = 'IN_USE', updated_at = NOW() 
                WHERE port_id = %s;
                """, (req.port_id,))

                # 4. Insert Active Charging Session
                cur.execute("""
                INSERT INTO charging_sessions (
                    port_id, user_identifier, start_time, session_status, energy_kwh
                ) VALUES (
                    %s, %s, NOW(), 'ACTIVE', 0.0
                )
                RETURNING session_id, port_id, user_identifier, start_time, end_time, energy_kwh, session_status;
                """, (req.port_id, req.user_identifier))
                new_session = cur.fetchone()

                # 5. Insert Status History Audit Record
                cur.execute("""
                INSERT INTO station_status_history (
                    port_id, old_status, new_status, changed_at, reason
                ) VALUES (
                    %s, 'AVAILABLE', 'IN_USE', NOW(), %s
                );
                """, (req.port_id, f"Session started by {req.user_identifier}"))

                conn.commit()
                return SessionSchema(**dict(new_session))

        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database transaction error: {str(e)}"
            )

@router.post("/end", response_model=SessionSchema)
def end_charging_session(req: EndSessionRequest):
    """
    Transactionally terminates an active charging session:
    1. Locks active session and associated port row
    2. Calculates / records metered energy consumed (kWh)
    3. Updates session end_time and marks status as 'COMPLETED'
    4. Transitions port status back to 'AVAILABLE'
    5. Logs status history audit entry
    6. Commits transaction
    """
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Fetch and Lock Active Session
                cur.execute("""
                SELECT session_id, port_id, user_identifier, start_time, end_time, energy_kwh, session_status
                FROM charging_sessions 
                WHERE session_id = %s 
                FOR UPDATE;
                """, (req.session_id,))
                sess = cur.fetchone()

                if not sess:
                    raise HTTPException(status_code=404, detail=f"Session with ID {req.session_id} not found")

                if sess['session_status'] != 'ACTIVE':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Session {req.session_id} is already '{sess['session_status']}'"
                    )

                port_id = sess['port_id']

                # 2. Lock the associated port
                cur.execute("SELECT port_id, status FROM charging_ports WHERE port_id = %s FOR UPDATE;", (port_id,))
                
                # 3. Calculate energy if not provided (realistic simulation based on elapsed duration)
                now_time = datetime.now()
                start_dt = sess['start_time'].replace(tzinfo=None)
                duration_hours = max(0.05, (now_time - start_dt).total_seconds() / 3600.0)
                
                final_kwh = req.energy_kwh
                if final_kwh is None or final_kwh <= 0:
                    # Calculate reasonable energy for standard ~30-50kW charger
                    final_kwh = round(duration_hours * 28.5, 2)

                # 4. Finalize Session Record
                cur.execute("""
                UPDATE charging_sessions 
                SET end_time = NOW(), energy_kwh = %s, session_status = 'COMPLETED'
                WHERE session_id = %s
                RETURNING session_id, port_id, user_identifier, start_time, end_time, energy_kwh, session_status;
                """, (final_kwh, req.session_id))
                updated_session = cur.fetchone()

                # 5. Transition Port back to AVAILABLE
                cur.execute("""
                UPDATE charging_ports 
                SET status = 'AVAILABLE', updated_at = NOW() 
                WHERE port_id = %s;
                """, (port_id,))

                # 6. Insert Status History Audit
                cur.execute("""
                INSERT INTO station_status_history (
                    port_id, old_status, new_status, changed_at, reason
                ) VALUES (
                    %s, 'IN_USE', 'AVAILABLE', NOW(), %s
                );
                """, (port_id, f"Session {req.session_id} completed. Delivered {final_kwh} kWh"))

                conn.commit()
                return SessionSchema(**dict(updated_session))

        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database transaction error: {str(e)}"
            )

@router.get("/history", response_model=List[SessionSchema])
def get_session_history(
    port_id: Optional[int] = Query(None, description="Filter history by port ID"),
    session_status: Optional[str] = Query(None, description="Filter by status (ACTIVE, COMPLETED, ABORTED)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Retrieves chronological charging session history.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
            SELECT session_id, port_id, user_identifier, start_time, end_time, energy_kwh, session_status
            FROM charging_sessions
            WHERE 1=1
            """
            params = []
            if port_id is not None:
                query += " AND port_id = %s"
                params.append(port_id)
            if session_status:
                query += " AND session_status = %s"
                params.append(session_status)

            query += " ORDER BY start_time DESC LIMIT %s OFFSET %s;"
            params.extend([limit, offset])

            cur.execute(query, params)
            rows = cur.fetchall()
            return [SessionSchema(**dict(r)) for r in rows]

@router.get("/ports/{port_id}/history", response_model=List[StatusHistorySchema])
def get_port_status_history(port_id: int, limit: int = Query(30, ge=1, le=100)):
    """
    Returns the temporal audit log of all status transitions for a specific charging port.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT history_id, port_id, old_status, new_status, changed_at, reason
            FROM station_status_history
            WHERE port_id = %s
            ORDER BY changed_at DESC
            LIMIT %s;
            """, (port_id, limit))
            rows = cur.fetchall()
            return [StatusHistorySchema(**dict(r)) for r in rows]
