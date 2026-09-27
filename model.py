from enum import IntEnum
from datetime import date

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Role(IntEnum):
    USER = 0
    EMPLOYEE = 1
    ADMIN = 7


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(20), unique=True, nullable=False)
    passwd = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.SmallInteger, nullable=False, default=Role.USER)

    def set_password(self, password):
        self.passwd = generate_password_hash(password)

    def check_password(self, password):
        if not self.passwd:
            return False
        # Совместимость со старым паролем из SQL-дампа ('1')
        if self.passwd.startswith(('pbkdf2:', 'scrypt:')):
            return check_password_hash(self.passwd, password)
        return self.passwd == password


class Organization(db.Model):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    inn = db.Column(db.String(12))
    phone = db.Column(db.String(20))
    contact_person = db.Column(db.String(120))
    address = db.Column(db.String(120))


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    specialization = db.Column(db.String(70))
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='SET NULL')
    )
    organization = db.relationship('Organization', backref='employees')


class Building(db.Model):
    __tablename__ = 'buildings'

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(100), nullable=False, unique=True)
    series = db.Column(db.String(20))
    year_built = db.Column(db.Integer)
    flats_count = db.Column(db.Integer, nullable=False)
    entrances = db.Column(db.Integer)


class System(db.Model):
    __tablename__ = 'systems'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    maintenance_interval_days = db.Column(db.Integer, nullable=False)
    responsible_org = db.Column(db.String(100))


class BuildingSystem(db.Model):
    __tablename__ = 'building_systems'

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(
        db.Integer,
        db.ForeignKey('buildings.id', ondelete='CASCADE'),
        nullable=False
    )
    system_id = db.Column(
        db.Integer,
        db.ForeignKey('systems.id', ondelete='CASCADE'),
        nullable=False
    )
    installation_date = db.Column(db.Date)
    status = db.Column(db.String(12), default='активна')
    notes = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint('building_id', 'system_id', name='uq_building_system'),
    )

    building = db.relationship('Building', backref='building_systems')
    system = db.relationship('System', backref='building_systems')


class Maintenance(db.Model):
    __tablename__ = 'maintenance'

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(
        db.Integer,
        db.ForeignKey('buildings.id', ondelete='RESTRICT'),
        nullable=False
    )
    system_id = db.Column(
        db.Integer,
        db.ForeignKey('systems.id', ondelete='RESTRICT'),
        nullable=False
    )
    scheduled_date = db.Column(db.Date, nullable=False)
    actual_date = db.Column(db.Date)
    performed_by = db.Column(
        db.Integer,
        db.ForeignKey('employees.id', ondelete='SET NULL')
    )
    contractor_org_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='SET NULL')
    )
    result = db.Column(db.String(12))

    building = db.relationship('Building', backref='maintenance_records')
    system = db.relationship('System', backref='maintenance_records')
    employee = db.relationship('Employee', backref='maintenance_records')
    contractor = db.relationship('Organization', backref='maintenance_records')


class Request(db.Model):
    __tablename__ = 'requests'

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(
        db.Integer,
        db.ForeignKey('buildings.id', ondelete='RESTRICT'),
        nullable=False
    )
    apartment = db.Column(db.String(5), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(12), nullable=False)
    status = db.Column(db.String(12), nullable=False, default='новая')
    created_date = db.Column(db.Date, nullable=False, default=date.today)
    completed_date = db.Column(db.Date)
    assigned_to = db.Column(
        db.Integer,
        db.ForeignKey('employees.id', ondelete='SET NULL')
    )

    building = db.relationship('Building', backref='requests')
    assigned_employee = db.relationship('Employee', backref='requests')