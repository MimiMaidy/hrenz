import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, redirect, url_for, request, flash, abort, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
import mimetypes
from sqlalchemy import select, func
import csv, io, re
from functools import wraps
from model import db, Role, User, Organization, Employee, Building, System, BuildingSystem, Maintenance, Request
from datetime import datetime, date

mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql+psycopg://hmsusr:hmspwd@localhost/hmsdb'
)
CSRFProtect(app)

# ===========================================================
#                                      SETUP
# ===========================================================
@app.context_processor
def inject_roles():
  return dict(Role=Role)

def admin_required(f):
    """Allow only authenticated admins."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != Role.ADMIN:
            flash("Доступ запрещён.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

def employee_required(f):
    """Allow admins and employees."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in (Role.ADMIN, Role.EMPLOYEE):
            flash("Доступ запрещён.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

@app.template_filter('DTF')
def format_datetime(value, format='%d.%m.%Y'):
  if value is None:
    return ''
  return value.strftime(format) 

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
  return db.session.get(User, int(user_id))

# ===========================================================
#                                   LOGIN
# ===========================================================
@app.route('/', methods=['GET', 'POST'])
def login():
  if request.method == "POST":
    user = User.query.filter_by(login=request.form['username']).first()
    # user = db.session.scalar(db.select(User).filter_by(username=request.form["username"]))
    if user and user.check_password(request.form["password"]):
      login_user(user)
      flash(f"Приветствую, {user.name}", "success")
      return redirect(url_for("dashboard"))
    flash("Неверный логин или пароль", "danger")
  return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
  flash(f"Досвидания, {current_user.name}", "info")
  logout_user()
  return redirect(url_for("login"))

# ===========================================================
#                                DASHBOARD
# ===========================================================
@app.route('/dashboard')
@login_required
def dashboard():
  return render_template('dashboard.html')

# ===========================================================
#                                USERS
# ===========================================================
@app.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.id).all()
    return render_template("users.html", users=all_users, Role=Role)

@app.route("/users/create", methods=["POST"])
@admin_required
def create_user():
    name     = request.form.get("name", "").strip()
    login    = request.form.get("login", "").strip()
    password = request.form.get("password", "")
    role_val = request.form.get("role", str(int(Role.USER)), type=str)

    if not name or not login or not password:
        flash("Имя, логин и пароль обязательны.", "error")
        return redirect(url_for("users"))

    # if len(password) < 6: +D+
    #     flash("Пароль должен содержать не менее 6 символов.", "error")
    #     return redirect(url_for("users"))

    if User.query.filter_by(login=login).first():
        flash(f"Логин «{login}» уже занят.", "error")
        return redirect(url_for("users"))

    try:
        role = Role(int(role_val))
    except (ValueError, KeyError):
        role = Role.USER

    user = User(name=name, login=login, role=int(role))
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f"Пользователь «{name}» создан.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/edit", methods=["POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    name = request.form.get("name", "").strip()
    login = request.form.get("login", "").strip()
    password = request.form.get("password", "")
    role_val = request.form.get("role", str(int(Role.USER)), type=str)

    if not name or not login:
        flash("Имя и логин обязательны.", "error")
        return redirect(url_for("users"))

    conflict = User.query.filter_by(login=login).first()
    if conflict and conflict.id != user_id:
        flash(f"Логин «{login}» уже занят.", "error")
        return redirect(url_for("users"))

    if password:
        # if len(password) < 6: +D+
        #     flash("Пароль должен содержать не менее 6 символов.", "error")
        #     return redirect(url_for("users"))
        user.set_password(password)

    try:
        role = Role(int(role_val))
    except (ValueError, KeyError):
        role = Role.USER

    # Prevent self-demotion
    if user.id == current_user.id:
        role = Role.ADMIN

    user.name  = name
    user.login = login
    user.role  = int(role)
    db.session.commit()

    flash(f"Пользователь «{user.name}» обновлён.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Нельзя удалить собственный аккаунт.", "error")
        return redirect(url_for("users"))

    name = user.name
    db.session.delete(user)
    db.session.commit()

    flash(f"Пользователь «{name}» удалён.", "success")
    return redirect(url_for("users"))

# ===========================================================
#                                ORGANIZATIONS
# ===========================================================
@app.route("/organizations")
@employee_required
def organizations():
    orgs = Organization.query.order_by(Organization.name).all()
    return render_template("organizations.html", organizations=orgs, Role=Role)


@app.route("/organizations/create", methods=["POST"])
@employee_required
def create_organization():
    name           = request.form.get("name", "").strip()
    inn            = request.form.get("inn", "").strip() or None
    phone          = request.form.get("phone", "").strip() or None
    contact_person = request.form.get("contact_person", "").strip() or None
    address        = request.form.get("address", "").strip() or None

    if not name:
        flash("Название обязательно.", "error")
        return redirect(url_for("organizations"))

    if inn and not re.fullmatch(r'\d{10}|\d{12}', inn):
        flash("ИНН должен содержать 10 или 12 цифр.", "error")
        return redirect(url_for("organizations"))

    if Organization.query.filter_by(name=name).first():
        flash(f"Организация «{name}» уже существует.", "error")
        return redirect(url_for("organizations"))

    org = Organization(name=name, inn=inn, phone=phone,
                       contact_person=contact_person, address=address)
    db.session.add(org)
    db.session.commit()

    flash(f"Организация «{name}» добавлена.", "success")
    return redirect(url_for("organizations"))


@app.route("/organizations/<int:org_id>/edit", methods=["POST"])
@employee_required
def edit_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    name = request.form.get("name", "").strip()
    inn  = request.form.get("inn", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    contact_person = request.form.get("contact_person", "").strip() or None
    address = request.form.get("address", "").strip() or None

    if not name:
        flash("Название обязательно.", "error")
        return redirect(url_for("organizations"))

    if inn and not re.fullmatch(r'\d{10}|\d{12}', inn):
        flash("ИНН должен содержать 10 или 12 цифр.", "error")
        return redirect(url_for("organizations"))

    conflict = Organization.query.filter_by(name=name).first()
    if conflict and conflict.id != org_id:
        flash(f"Организация «{name}» уже существует.", "error")
        return redirect(url_for("organizations"))

    org.name = name
    org.inn = inn
    org.phone = phone
    org.contact_person = contact_person
    org.address = address
    db.session.commit()

    flash(f"Организация «{name}» обновлена.", "success")
    return redirect(url_for("organizations"))


@app.route("/organizations/<int:org_id>/delete", methods=["POST"])
@admin_required  # delete is admin-only
def delete_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    name = org.name
    db.session.delete(org)
    db.session.commit()

    flash(f"Организация «{name}» удалена.", "success")
    return redirect(url_for("organizations"))

@app.route('/organizations/<int:org_id>/employees')
def org_employees(org_id):
    organization = Organization.query.get_or_404(org_id)
    organizations = Organization.query.order_by(Organization.name).all()
    return render_template('employees.html',
                           organization=organization,
                           employees=organization.employees,
                           organizations=organizations,
                           current_org_id=org_id)  
# ===========================================================
#                                EMPLOYEES
# ===========================================================
def redirect_after_employee(form_data):
    org_id = form_data.get('return_org_id', type=int)
    if org_id:
        return redirect(url_for('org_employees', org_id=org_id))
    return redirect(url_for('employees'))

@app.route("/employees")
@employee_required
def employees():
    all_employees = Employee.query.order_by(Employee.full_name).all()
    organizations = Organization.query.order_by(Organization.name).all()
    return render_template("employees.html", employees=all_employees,
                           organizations=organizations, Role=Role)

@app.route("/employees/create", methods=["POST"])
@employee_required
def create_employee():
    full_name = request.form.get("full_name", "").strip()
    position = request.form.get("position", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    specialization = request.form.get("specialization", "").strip() or None
    org_id = request.form.get("organization_id") or None

    if not full_name:
        flash("ФИО обязательно.", "error")
        return redirect(url_for("employees"))

    emp = Employee(full_name=full_name, position=position, phone=phone,
                   specialization=specialization, organization_id=org_id)
    db.session.add(emp)
    db.session.commit()

    flash(f"Сотрудник «{full_name}» добавлен.", "success")
    return redirect_after_employee(request.form)


@app.route("/employees/<int:emp_id>/edit", methods=["POST"])
@employee_required
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    full_name = request.form.get("full_name", "").strip()
    position = request.form.get("position", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    specialization = request.form.get("specialization", "").strip() or None
    org_id = request.form.get("organization_id") or None

    if not full_name:
        flash("ФИО обязательно.", "error")
        return redirect(url_for("employees"))

    emp.full_name = full_name
    emp.position = position
    emp.phone = phone
    emp.specialization = specialization
    emp.organization_id = org_id
    db.session.commit()

    flash(f"Сотрудник «{full_name}» обновлён.", "success")
    return redirect_after_employee(request.form)


@app.route("/employees/<int:emp_id>/delete", methods=["POST"])
@admin_required
def delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    org_id = emp.organization_id # store org
    name = emp.full_name
    db.session.delete(emp)
    db.session.commit()

    flash(f"Сотрудник «{name}» удалён.", "success")
    if org_id:
        return redirect(url_for('org_employees', org_id=org_id))
    return redirect(url_for('employees'))

# ===========================================================
#                                BUILDINGS
# ===========================================================
@app.route("/buildings")
@employee_required
def buildings():
    return render_template("buildings.html",
                           buildings=Building.query.order_by(Building.address).all(),
                           Role=Role)

@app.route("/buildings/<int:building_id>/systems")
@employee_required
def building_systems_by_building(building_id):
    building = Building.query.get_or_404(building_id)
    return render_template("building_systems.html",
                           building=building,                          # current building
                           building_systems=BuildingSystem.query.filter_by(building_id=building_id).all(),
                           buildings=Building.query.order_by(Building.address).all(),
                           systems=System.query.order_by(System.name).all(),
                           Role=Role)

@app.route("/buildings/create", methods=["POST"])
@employee_required
def create_building():
    address = request.form.get("address", "").strip()
    series  = request.form.get("series", "").strip() or None
    year_built  = request.form.get("year_built") or None
    flats_count = request.form.get("flats_count")
    entrances = request.form.get("entrances") or None

    if not address or not flats_count:
        flash("Адрес и количество квартир обязательны.", "error")
        return redirect(url_for("buildings"))

    if Building.query.filter_by(address=address).first():
        flash(f"Здание «{address}» уже существует.", "error")
        return redirect(url_for("buildings"))

    db.session.add(Building(address=address, series=series, year_built=year_built,
                            flats_count=int(flats_count), entrances=entrances))
    db.session.commit()
    flash(f"Здание «{address}» добавлено.", "success")
    return redirect(url_for("buildings"))

@app.route("/buildings/<int:building_id>/edit", methods=["POST"])
@employee_required
def edit_building(building_id):
    b = Building.query.get_or_404(building_id)
    address = request.form.get("address", "").strip()
    flats_count = request.form.get("flats_count")

    if not address or not flats_count:
        flash("Адрес и количество квартир обязательны.", "error")
        return redirect(url_for("buildings"))

    conflict = Building.query.filter_by(address=address).first()
    if conflict and conflict.id != building_id:
        flash(f"Здание «{address}» уже существует.", "error")
        return redirect(url_for("buildings"))

    b.address = address
    b.series = request.form.get("series", "").strip() or None
    b.year_built  = request.form.get("year_built") or None
    b.flats_count = int(flats_count)
    b.entrances = request.form.get("entrances") or None
    db.session.commit()
    flash(f"Здание «{address}» обновлено.", "success")
    return redirect(url_for("buildings"))

@app.route("/buildings/<int:building_id>/delete", methods=["POST"])
@admin_required
def delete_building(building_id):
    b = Building.query.get_or_404(building_id)
    db.session.delete(b)
    db.session.commit()
    flash(f"Здание «{b.address}» удалено.", "success")
    return redirect(url_for("buildings"))

# ===========================================================
#                                SYSTEMS
# ===========================================================
@app.route("/systems")
@employee_required
def systems():
    return render_template("systems.html",
                           systems=System.query.order_by(System.name).all(),
                           Role=Role)

@app.route("/systems/create", methods=["POST"])
@employee_required
def create_system():
    name = request.form.get("name", "").strip()
    interval = request.form.get("maintenance_interval_days")
    org = request.form.get("responsible_org", "").strip() or None

    if not name or not interval:
        flash("Название и интервал ТО обязательны.", "error")
        return redirect(url_for("systems"))

    if System.query.filter_by(name=name).first():
        flash(f"Система «{name}» уже существует.", "error")
        return redirect(url_for("systems"))

    db.session.add(System(name=name, maintenance_interval_days=int(interval), responsible_org=org))
    db.session.commit()
    flash(f"Система «{name}» добавлена.", "success")
    return redirect(url_for("systems"))

@app.route("/systems/<int:system_id>/edit", methods=["POST"])
@employee_required
def edit_system(system_id):
    s = System.query.get_or_404(system_id)
    name = request.form.get("name", "").strip()
    interval = request.form.get("maintenance_interval_days")

    if not name or not interval:
        flash("Название и интервал ТО обязательны.", "error")
        return redirect(url_for("systems"))

    conflict = System.query.filter_by(name=name).first()
    if conflict and conflict.id != system_id:
        flash(f"Система «{name}» уже существует.", "error")
        return redirect(url_for("systems"))

    s.name = name
    s.maintenance_interval_days = int(interval)
    s.responsible_org = request.form.get("responsible_org", "").strip() or None
    db.session.commit()
    flash(f"Система «{name}» обновлена.", "success")
    return redirect(url_for("systems"))

@app.route("/systems/<int:system_id>/delete", methods=["POST"])
@admin_required
def delete_system(system_id):
    s = System.query.get_or_404(system_id)
    db.session.delete(s)
    db.session.commit()
    flash(f"Система «{s.name}» удалена.", "success")
    return redirect(url_for("systems"))

# ===========================================================
#                             BUILDING_SYSTEMS
# ===========================================================
def redirect_after_bs(form_data): # Redirector
    building_id = form_data.get('return_building_id', type=int)
    if building_id:
        return redirect(url_for('building_systems_by_building', building_id=building_id))
    return redirect(url_for('building_systems'))

@app.route("/building_systems")
@employee_required
def building_systems():
    return render_template("building_systems.html",
                           building_systems=BuildingSystem.query.all(),
                           buildings=Building.query.order_by(Building.address).all(),
                           systems=System.query.order_by(System.name).all(),
                           Role=Role)

@app.route("/building_systems/create", methods=["POST"])
@employee_required
def create_building_system():
    building_id = request.form.get("building_id")
    system_id = request.form.get("system_id")
    installation_date = request.form.get("installation_date") or None
    status = request.form.get("status", "активна")
    notes = request.form.get("notes", "").strip() or None

    if not building_id or not system_id:
        flash("Здание и система обязательны.", "error")
        return redirect(url_for("building_systems"))

    if BuildingSystem.query.filter_by(building_id=int(building_id), system_id=int(system_id)).first():
        flash("Такая связь здания и системы уже существует.", "error")
        return redirect(url_for("building_systems"))

    db.session.add(BuildingSystem(building_id=int(building_id), system_id=int(system_id),
                                  installation_date=installation_date, status=status, notes=notes))
    db.session.commit()
    flash("Запись добавлена.", "success")
    return redirect_after_bs(request.form)

@app.route("/building_systems/<int:bs_id>/edit", methods=["POST"])
@employee_required
def edit_building_system(bs_id):
    bs = BuildingSystem.query.get_or_404(bs_id)
    building_id = request.form.get("building_id")
    system_id = request.form.get("system_id")

    if not building_id or not system_id:
        flash("Здание и система обязательны.", "error")
        return redirect(url_for("building_systems"))

    conflict = BuildingSystem.query.filter_by(building_id=int(building_id), system_id=int(system_id)).first()
    if conflict and conflict.id != bs_id:
        flash("Такая связь здания и системы уже существует.", "error")
        return redirect(url_for("building_systems"))

    bs.building_id = int(building_id)
    bs.system_id = int(system_id)
    bs.installation_date = request.form.get("installation_date") or None
    bs.status = request.form.get("status", "активна")
    bs.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    flash("Запись обновлена.", "success")
    return redirect_after_bs(request.form)

@app.route("/building_systems/<int:bs_id>/delete", methods=["POST"])
@admin_required
def delete_building_system(bs_id):
    bs = BuildingSystem.query.get_or_404(bs_id)
    building_id = bs.building_id  # store before delete
    db.session.delete(bs)
    db.session.commit()
    flash("Запись удалена.", "success")
    return redirect(url_for('building_systems_by_building', building_id=building_id))

# ===========================================================
#                                MAINTENANCE
# ===========================================================
@app.route("/maintenance")
@employee_required
def maintenance():
    return render_template("maintenance.html",
                           maintenance_list=Maintenance.query.order_by(Maintenance.scheduled_date.desc()).all(),
                           buildings=Building.query.order_by(Building.address).all(),
                           systems=System.query.order_by(System.name).all(),
                           employees=Employee.query.order_by(Employee.full_name).all(),
                           organizations=Organization.query.order_by(Organization.name).all(),
                           Role=Role)

@app.route("/maintenance/create", methods=["POST"])
@employee_required
def create_maintenance():
    building_id = request.form.get("building_id")
    system_id = request.form.get("system_id")
    scheduled_date = request.form.get("scheduled_date")
    actual_date = request.form.get("actual_date") or None
    performed_by = request.form.get("performed_by") or None
    contractor_org_id = request.form.get("contractor_org_id") or None
    result = request.form.get("result") or None

    if not building_id or not system_id or not scheduled_date:
        flash("Здание, система и плановая дата обязательны.", "error")
        return redirect(url_for("maintenance"))

    db.session.add(Maintenance(building_id=int(building_id), system_id=int(system_id),
                               scheduled_date=scheduled_date, actual_date=actual_date,
                               performed_by=performed_by, contractor_org_id=contractor_org_id,
                               result=result))
    db.session.commit()
    flash("Запись ТО добавлена.", "success")
    return redirect(url_for("maintenance"))

@app.route("/maintenance/<int:m_id>/edit", methods=["POST"])
@employee_required
def edit_maintenance(m_id):
    m = Maintenance.query.get_or_404(m_id)
    building_id = request.form.get("building_id")
    system_id = request.form.get("system_id")
    scheduled_date = request.form.get("scheduled_date")

    if not building_id or not system_id or not scheduled_date:
        flash("Здание, система и плановая дата обязательны.", "error")
        return redirect(url_for("maintenance"))

    m.building_id = int(building_id)
    m.system_id = int(system_id)
    m.scheduled_date = scheduled_date
    m.actual_date = request.form.get("actual_date") or None
    m.performed_by = request.form.get("performed_by") or None
    m.contractor_org_id = request.form.get("contractor_org_id") or None
    m.result = request.form.get("result") or None
    db.session.commit()
    flash("Запись ТО обновлена.", "success")
    return redirect(url_for("maintenance"))

@app.route("/maintenance/<int:m_id>/delete", methods=["POST"])
@admin_required
def delete_maintenance(m_id):
    m = Maintenance.query.get_or_404(m_id)
    db.session.delete(m)
    db.session.commit()
    flash("Запись ТО удалена.", "success")
    return redirect(url_for("maintenance"))

# ===========================================================
#                                REQUESTS
# ===========================================================
@app.route("/requests")
@employee_required
def requests():
    return render_template("requests.html",
                           requests=Request.query.order_by(Request.created_date.desc()).all(),
                           buildings=Building.query.order_by(Building.address).all(),
                           employees=Employee.query.order_by(Employee.full_name).all(),
                           Role=Role)

@app.route("/requests/create", methods=["POST"])
@employee_required
def create_request():
    building_id = request.form.get("building_id")
    apartment = request.form.get("apartment", "").strip()
    description = request.form.get("description", "").strip()
    priority = request.form.get("priority", "низкий")
    status = request.form.get("status", "новая")
    completed_date = request.form.get("completed_date") or None
    assigned_to = request.form.get("assigned_to") or None

    if not building_id or not apartment or not description:
        flash("Здание, квартира и описание обязательны.", "error")
        return redirect(url_for("requests"))

    db.session.add(Request(building_id=int(building_id), apartment=apartment,
                           description=description, priority=priority, status=status,
                           completed_date=completed_date, assigned_to=assigned_to))
    db.session.commit()
    flash("Заявка добавлена.", "success")
    return redirect(url_for("requests"))

@app.route("/requests/<int:req_id>/edit", methods=["POST"])
@employee_required
def edit_request(req_id):
    r = Request.query.get_or_404(req_id)
    building_id = request.form.get("building_id")
    apartment = request.form.get("apartment", "").strip()
    description = request.form.get("description", "").strip()

    if not building_id or not apartment or not description:
        flash("Здание, квартира и описание обязательны.", "error")
        return redirect(url_for("requests"))

    r.building_id = int(building_id)
    r.apartment = apartment
    r.description = description
    r.priority = request.form.get("priority", "низкий")
    r.status = request.form.get("status", "новая")
    r.completed_date = request.form.get("completed_date") or None
    r.assigned_to = request.form.get("assigned_to") or None
    db.session.commit()
    flash("Заявка обновлена.", "success")
    return redirect(url_for("requests"))

@app.route("/requests/<int:req_id>/delete", methods=["POST"])
@admin_required
def delete_request(req_id):
    r = Request.query.get_or_404(req_id)
    db.session.delete(r)
    db.session.commit()
    flash("Заявка удалена.", "success")
    return redirect(url_for("requests"))

# ===========================================================
#                                   REPORTS
# ===========================================================
@app.route('/report_maintenance')
@employee_required
def report_maintenance():
    date_from_str = request.args.get("date_from")
    date_to_str = request.args.get("date_to")
    building_id = request.args.get("building_id", type=int)
    system_id = request.args.get("system_id", type=int)
    result_filter = request.args.get("result")

    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else None
    date_to   = datetime.strptime(date_to_str,   "%Y-%m-%d").date() if date_to_str   else None


    query = Maintenance.query

    if date_from:
        query = query.filter(Maintenance.scheduled_date >= date_from)
    if date_to:
        query = query.filter(Maintenance.scheduled_date <= date_to)
    if building_id:
        query = query.filter(Maintenance.building_id == building_id)
    if system_id:
        query = query.filter(Maintenance.system_id == system_id)
    if result_filter:
        query = query.filter(Maintenance.result == result_filter)

    records = query.order_by(Maintenance.scheduled_date.desc()).all()

    return render_template("report_maintenance.html",
                           records=records,
                           buildings=Building.query.order_by(Building.address).all(),
                           systems=System.query.order_by(System.name).all(),
                           date_from=date_from or "",
                           date_to=date_to or "",
                           building_id=building_id,
                           system_id=system_id,
                           result_filter=result_filter or "",
                           Role=Role)

@app.route("/reports_requests")
@employee_required
def report_requests():
    date_from_str = request.args.get("date_from")
    date_to_str   = request.args.get("date_to")
    building_id   = request.args.get("building_id", type=int)
    status_filter   = request.args.get("status")
    priority_filter = request.args.get("priority")

    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else None
    date_to   = datetime.strptime(date_to_str,   "%Y-%m-%d").date() if date_to_str   else None

    query = Request.query

    if date_from:
        query = query.filter(Request.created_date >= date_from)
    if date_to:
        query = query.filter(Request.created_date <= date_to)
    if building_id:
        query = query.filter(Request.building_id == building_id)
    if status_filter:
        query = query.filter(Request.status == status_filter)
    if priority_filter:
        query = query.filter(Request.priority == priority_filter)

    records = query.order_by(Request.created_date.desc()).all()

    return render_template("report_requests.html",
                           records=records,
                           buildings=Building.query.order_by(Building.address).all(),
                           date_from=date_from_str or "",
                           date_to=date_to_str or "",
                           building_id=building_id,
                           status_filter=status_filter or "",
                           priority_filter=priority_filter or "",
                           Role=Role)
# ===========================================================
#                                   M A I N
# ===========================================================
if __name__ == "__main__":
  app.run(debug=True)