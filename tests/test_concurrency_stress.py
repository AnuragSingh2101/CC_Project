"""
Concurrency and race condition tests.
Reserves concurrently against the same lot using multiple threads to prove anti-oversell safety.
"""
import pytest
import os
import concurrent.futures
from datetime import date, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from database.connection import Base
import database.schema
from services.inventory_service import create_lot
from services.request_service import create_request
from services.reservation_service import make_reservation
from models.inventory import InventoryLot
from models.organization import Organization


class TestConcurrentReservations:
    """Proves oversell safety under multi-threaded concurrent reservation attempts."""

    def test_concurrent_reservations_cannot_oversell(self, tmp_path, future_date):
        """
        Setup a lot with exactly 10 units.
        Launch 5 threads, each attempting to reserve 3 units (total 15 units demanded).
        At most 3 threads can succeed (9 units reserved).
        Total reserved units must NEVER exceed total units (10).
        """
        db_path = str(tmp_path / "concurrency_test.db")
        eng = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30}
        )

        @event.listens_for(eng, "connect")
        def set_sqlite_pragmas(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

        Base.metadata.create_all(bind=eng)
        SessionLocal = sessionmaker(bind=eng)

        setup_db = SessionLocal()
        bb = Organization(name="Concurrency BB", type="blood_bank", city="Bengaluru", state="Karnataka")
        hosp = Organization(name="Concurrency Hosp", type="hospital", city="Bengaluru", state="Karnataka")
        setup_db.add_all([bb, hosp])
        setup_db.flush()

        lot = create_lot(
            db=setup_db,
            blood_bank_id=bb.id,
            blood_group="O-",
            component="packed_red_cells",
            units_total=10,
            expiry_date=future_date
        )
        setup_db.commit()
        lot_id = lot.id

        req_ids = []
        for _ in range(5):
            req = create_request(
                db=setup_db,
                hospital_id=hosp.id,
                blood_group="O-",
                units_requested=3,
                urgency="critical"
            )
            req_ids.append(req.id)
        setup_db.commit()
        setup_db.close()

        successes = []
        failures = []

        def worker_reserve(req_id):
            worker_db = SessionLocal()
            try:
                res = make_reservation(
                    db=worker_db,
                    request_id=req_id,
                    inventory_lot_id=lot_id,
                    units_to_reserve=3
                )
                worker_db.commit()
                return ("SUCCESS", res.id)
            except Exception as e:
                worker_db.rollback()
                return ("FAILURE", str(e))
            finally:
                worker_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_reserve, req_ids[i]) for i in range(5)]
            for fut in concurrent.futures.as_completed(futures):
                status, msg = fut.result()
                if status == "SUCCESS":
                    successes.append(msg)
                else:
                    failures.append(msg)

        verify_db = SessionLocal()
        final_lot = verify_db.get(InventoryLot, lot_id)

        # Verification of anti-oversell guarantee:
        assert final_lot.units_reserved <= final_lot.units_total
        assert len(successes) == 3
        assert len(failures) == 2
        assert final_lot.units_reserved == 9
        assert final_lot.available_units == 1

        verify_db.close()
        eng.dispose()
