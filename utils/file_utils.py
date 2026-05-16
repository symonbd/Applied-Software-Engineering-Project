from config import QDA_EXTENSIONS, PRIMARY_EXTENSIONS

def valid_file(filename):

    filename = filename.lower()

    for ext in QDA_EXTENSIONS + PRIMARY_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False