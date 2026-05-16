import hashlib

def sha256_file(path):

    sha = hashlib.sha256()

    with open(path,"rb") as f:

        while True:

            chunk = f.read(8192)

            if not chunk:
                break

            sha.update(chunk)

    return sha.hexdigest()