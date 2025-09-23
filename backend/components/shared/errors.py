class DatabaseError(Exception):
    """Base exception for database-related errors"""

    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails"""

    pass


class TransactionError(DatabaseError):
    """Raised when database transaction fails"""

    pass
