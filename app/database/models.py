from sqlalchemy import String, BigInteger, Text, DateTime, func, Integer, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase


class Base(DeclarativeBase):
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class UserSpeciality(Base):
    __tablename__ = 'user_specialities'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    speciality_id = Column(Integer, ForeignKey('specialities.id'))

    user = relationship("User", back_populates="user_specialities")
    speciality = relationship("Speciality", back_populates="user_specialities")

class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sms_exams: Mapped[Text] = mapped_column(Text)
    sms_entered_study: Mapped[Text] = mapped_column(Text)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="answers")


class Speciality(Base):
    __tablename__ = "specialities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    call_back: Mapped[str] = mapped_column(Text)

    user_specialities = relationship("UserSpeciality", back_populates="speciality", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str] = mapped_column(String(150), nullable=True)
    teleg_phone: Mapped[str] = mapped_column(String(13), nullable=True)
    reg_phone: Mapped[int] = mapped_column(Integer, nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=True)

    answers = relationship("Answer", back_populates="user")
    user_specialities = relationship("UserSpeciality", back_populates="user", cascade="all, delete-orphan")


class DellUser(Base):
    __tablename__ = "dell_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str] = mapped_column(String(150), nullable=True)
    teleg_phone: Mapped[str] = mapped_column(String(13), nullable=True)
    reg_phone: Mapped[int] = mapped_column(Integer, nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=True)
    user_speciality: Mapped[str] = mapped_column(Text, nullable=True)


