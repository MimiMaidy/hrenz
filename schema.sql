-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»ÐµÐ¹
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    login varchar(20),
    passwd varchar(256),
    name varchar(100),
    role SMALLINT null default 0
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° Ð¾Ñ€Ð³Ð°Ð½Ð¸Ð·Ð°Ñ†Ð¸Ð¹ (Ð¿Ð¾Ð´Ñ€ÑÐ´Ñ‡Ð¸ÐºÐ¾Ð²)
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name varchar(100) NOT NULL UNIQUE,
    inn varchar(12),
    phone varchar(20),
    contact_person varchar(120),
    address varchar(120)
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¾Ð² (Ñ Ð¿Ñ€Ð¸Ð²ÑÐ·ÐºÐ¾Ð¹ Ðº Ð¾Ñ€Ð³Ð°Ð½Ð¸Ð·Ð°Ñ†Ð¸Ð¸)
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    full_name varchar(120) NOT NULL,
    position varchar(100),
    phone varchar(20),
    specialization varchar(70),
    organization_id INTEGER,
    CONSTRAINT fk_employees_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° Ð´Ð¾Ð¼Ð¾Ð²
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    address varchar(100) NOT NULL UNIQUE,
    series varchar(20),
    year_built INTEGER,
    flats_count INTEGER NOT NULL,
    entrances INTEGER
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° Ð¸Ð½Ð¶ÐµÐ½ÐµÑ€Ð½Ñ‹Ñ… ÑÐ¸ÑÑ‚ÐµÐ¼
CREATE TABLE IF NOT EXISTS systems (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name varchar(100) NOT NULL UNIQUE,
    maintenance_interval_days INTEGER NOT NULL,
    responsible_org varchar(100)
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° ÑÐ²ÑÐ·Ð¸ Ð´Ð¾Ð¼Ð¾Ð² Ð¸ ÑÐ¸ÑÑ‚ÐµÐ¼
CREATE TABLE IF NOT EXISTS building_systems (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    building_id INTEGER NOT NULL,
    system_id INTEGER NOT NULL,
    installation_date DATE,
    status varchar(12) DEFAULT 'Ð°ÐºÑ‚Ð¸Ð²Ð½Ð°',
    notes TEXT,
    CONSTRAINT fk_bs_building FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE CASCADE,
    CONSTRAINT fk_bs_system FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
    CONSTRAINT uq_building_system UNIQUE (building_id, system_id)
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° Ð¿Ð»Ð°Ð½Ð¾Ð²Ð¾Ð³Ð¾ Ð¢Ðž
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    building_id INTEGER NOT NULL,
    system_id INTEGER NOT NULL,
    scheduled_date DATE NOT NULL,
    actual_date DATE,
    performed_by INTEGER,
    contractor_org_id INTEGER,
    result varchar(12),
    CONSTRAINT fk_maint_building FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE RESTRICT,
    CONSTRAINT fk_maint_system FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE RESTRICT,
    CONSTRAINT fk_maint_employee FOREIGN KEY (performed_by) REFERENCES employees(id) ON DELETE SET NULL,
    CONSTRAINT fk_maint_contractor FOREIGN KEY (contractor_org_id) REFERENCES organizations(id) ON DELETE SET NULL
);

-- Ð¢Ð°Ð±Ð»Ð¸Ñ†Ð° Ð·Ð°ÑÐ²Ð¾Ðº Ð¶Ð¸Ð»ÑŒÑ†Ð¾Ð²
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    building_id INTEGER NOT NULL,
    apartment VARCHAR(5) NOT NULL,
    description TEXT NOT NULL,
    priority varchar(12) NOT NULL,
    status varchar(12) NOT NULL DEFAULT 'Ð½Ð¾Ð²Ð°Ñ',
    created_date DATE NOT NULL DEFAULT CURRENT_DATE,
    completed_date DATE,
    assigned_to INTEGER,
    CONSTRAINT fk_req_building FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE RESTRICT,
    CONSTRAINT fk_req_employee FOREIGN KEY (assigned_to) REFERENCES employees(id) ON DELETE SET NULL
);

-- Ð˜Ð½Ð´ÐµÐºÑÑ‹ Ð²Ð½ÐµÑˆÐ½Ð¸Ñ… ÐºÐ»ÑŽÑ‡ÐµÐ¹
-- employees
CREATE INDEX IF NOT EXISTS idx_employees_organization_id ON employees(organization_id);

-- building_systems
CREATE INDEX IF NOT EXISTS idx_building_systems_building_id ON building_systems(building_id);
CREATE INDEX IF NOT EXISTS idx_building_systems_system_id ON building_systems(system_id);

-- maintenance
CREATE INDEX IF NOT EXISTS idx_maintenance_building_id ON maintenance(building_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_system_id ON maintenance(system_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_performed_by ON maintenance(performed_by);
CREATE INDEX IF NOT EXISTS idx_maintenance_contractor_org_id ON maintenance(contractor_org_id);

-- requests
CREATE INDEX IF NOT EXISTS idx_requests_building_id ON requests(building_id);
CREATE INDEX IF NOT EXISTS idx_requests_assigned_to ON requests(assigned_to);
insert into users (login,passwd,role,name) values ('admin','1',7,'ÐÐ´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¾Ñ€ ÑÐ¸ÑÑ‚ÐµÐ¼Ñ‹'); 
