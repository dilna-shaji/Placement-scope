class ApiError(Exception):
    def __init__(self, message, status=400, fields=None, code=None):
        super().__init__(message)
        self.message, self.status, self.fields, self.code = message, status, fields or {}, code
