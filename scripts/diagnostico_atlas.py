import getpass
import os

from pymongo import MongoClient
from pymongo.errors import PyMongoError

BASES_SISTEMA = {"admin", "local", "config"}


def main():
    uri = os.getenv("MONGO_URI") or getpass.getpass("URI de conexión de MongoDB Atlas: ")
    cliente = None
    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
        cliente.admin.command("ping")
        servidores = sorted(f"{host}:{puerto}" for host, puerto in cliente.nodes)
        print("Conexión exitosa. Servidores del clúster:")
        for servidor in servidores:
            print(f"  {servidor}")

        bases = [b for b in cliente.list_database_names() if b not in BASES_SISTEMA]
        if not bases:
            print("\nEl clúster no tiene bases de datos de usuario.")
        for nombre in bases:
            db = cliente[nombre]
            print(f"\nBase de datos: {nombre}")
            colecciones = db.list_collection_names()
            if not colecciones:
                print("  (sin colecciones)")
            for coleccion in sorted(colecciones):
                print(f"  {coleccion}: {db[coleccion].count_documents({})} documentos")
    except PyMongoError as error:
        print(f"Error de MongoDB: {error}")
        raise SystemExit(1)
    finally:
        if cliente is not None:
            cliente.close()


if __name__ == "__main__":
    main()
