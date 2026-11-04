
import getpass
import re

from pwdlib import PasswordHash
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Role, User

password_hasher = PasswordHash.recommended()

def main() -> None:
    print("=== STAD: Crear administrador inicial ===")

    email = input("Correo electrónico: ").strip().lower()
    full_name = input("Nombre completo: ").strip()

    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        print("Error: correo electrónico inválido.")
        return

    if not full_name or len(full_name) > 150:
        print("Error: nombre inválido.")
        return

    with SessionLocal() as session:
        existing_user = session.scalar(
            select(User).where(User.email == email)
        )

        if existing_user is not None:
            print("Error: ya existe una cuenta con ese correo.")
            return

        admin_role = session.scalar(
            select(Role).where(Role.code == "ADMIN")
        )

        if admin_role is None:
            print("Error: el rol ADMIN no existe.")
            return

        password = getpass.getpass("Contraseña temporal: ")
        confirmation = getpass.getpass("Confirmar contraseña: ")

        if len(password) < 12:
            print("Error: se requieren al menos 12 caracteres.")
            return

        if password != confirmation:
            print("Error: las contraseñas no coinciden.")
            return

        admin = User(
            email=email,
            full_name=full_name,
            password_hash=password_hasher.hash(password),
            role_id=admin_role.id,
            is_active=True,
            must_change_password=True,
            token_version=1,
        )

        session.add(admin)
        session.commit()
        session.refresh(admin)

        print(f"Administrador creado. ID: {admin.id}")
        print("El cambio de contraseña será obligatorio al iniciar sesión.")


if __name__ == "__main__":
    main()
