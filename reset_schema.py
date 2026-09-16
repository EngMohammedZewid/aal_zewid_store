import argparse

from core.db import DEFAULT_DB_PATH, reset_db


def parse_args():
    parser = argparse.ArgumentParser(
        description="Reset StoreManager database schema to empty state."
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database file (default: {DEFAULT_DB_PATH})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    reset_db(args.db_path)
    print(f"Database schema reset successfully: {args.db_path}")
    print("All tables are now empty and ready for new data.")


if __name__ == "__main__":
    main()
