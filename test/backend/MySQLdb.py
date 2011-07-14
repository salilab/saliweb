# Dummy implementation to test the Database._connect() method

OperationalError = 'Dummy MySQL OperationalError'

def connect(*args, **keys):
    return [args, keys]
