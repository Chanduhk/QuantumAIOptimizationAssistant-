from backend.app.database.db import create_tables, init_db
from backend.app.models import BehaviorData, Task


def main() -> None:
    """Initialize the configured database and create all behavior tables."""
    init_db()

    # Importing the models ensures they are registered on the shared SQLAlchemy Base.
    _ = (Task, BehaviorData)

    create_tables()
    print("Database initialized successfully")


if __name__ == "__main__":
    main()
