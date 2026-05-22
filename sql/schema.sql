-- schema.sql
-- PostgreSQL schema for Smart Fleet Telematics Analytics
-- Reflects the actual processed_telematics.csv column set.

-- --------------------------------------------------------
-- PROCESSED TELEMATICS (wide format, one row per reading)
-- --------------------------------------------------------

DROP TABLE IF EXISTS fleet_telematics CASCADE;

CREATE TABLE fleet_telematics (
    id                              SERIAL PRIMARY KEY,

    -- Identity
    device_id                       VARCHAR(64)   NOT NULL,
    timestamp                       TIMESTAMP     NOT NULL,
    date                            DATE,
    hour                            SMALLINT,
    day_of_week                     SMALLINT,     -- 0=Monday

    -- Alarm
    alarm_class                     SMALLINT      NOT NULL DEFAULT 0,
    -- 0=Normal 1=LowRisk 2=MedRisk 3=HighRisk 4=Critical 5=Emergency

    -- GPS
    lat                             DOUBLE PRECISION,
    lng                             DOUBLE PRECISION,
    altitude                        DOUBLE PRECISION,

    -- Engine
    engine_rpm                      FLOAT,
    calculated_engine_load          FLOAT,
    engine_coolant_temperature      FLOAT,
    run_time_since_engine_start     FLOAT,

    -- Motion / speed
    vehicle_speed                   FLOAT,
    is_idle                         SMALLINT,     -- 0/1

    -- Acceleration
    acceleration_x                  FLOAT,
    acceleration_y                  FLOAT,
    acceleration_z                  FLOAT,

    -- Throttle
    throttle_position               FLOAT,
    relative_throttle_position      FLOAT,
    absolute_throttle_position_b    FLOAT,
    absolute_throttle_position_d    FLOAT,
    absolute_throttle_position_e    FLOAT,
    commanded_throttle_actuator     FLOAT,

    -- Fuel
    fuel_system_status              FLOAT,
    fuel_tank_level_input           FLOAT,
    fuel_rail_gauge_pressure        FLOAT,
    fuel_air_commanded_equivalence_rate FLOAT,
    short_term_fuel_trim_bank_1     FLOAT,
    long_term_fuel_trim_bank_1      FLOAT,
    commanded_evaporative_purge     FLOAT,

    -- Air / intake
    air_intake_temperature          FLOAT,
    intake_manifold_absolute_pressure FLOAT,
    maf_air_flow_rate               FLOAT,
    absolulte_barometric_pressure   FLOAT,
    ambient_air_temperature         FLOAT,

    -- Battery
    internal_battery                FLOAT,
    external_battery                FLOAT,
    control_module_voltage          FLOAT,

    -- Torque
    engine_reference_torque         FLOAT,
    actual_engin___percent_torque   FLOAT,
    drivers_demand_engin___percent_torque FLOAT,

    -- Oxygen sensors
    oxygen_sensor_1___b_short_term_fuel_trim FLOAT,
    oxygen_sensor_2___b_short_term_fuel_trim FLOAT,
    oxygen_sensor_1___ab_fuel_air_equivalence_ratio FLOAT,
    oxygen_sensors_present_in_2_banks FLOAT,

    -- Misc OBD
    timing_advance                  FLOAT,
    absolute_load_value             FLOAT,
    distance_traveled_with_mil_on   FLOAT,
    distance_traveled_since_codes_cleared FLOAT,
    warm_ups_since_codes_cleared    FLOAT,
    catalyst_temperature_bank_1_sensor_1 FLOAT,
    obd_standards_this_vehicle_conforms_to FLOAT,
    monitor_status_this_drive_cycle FLOAT,
    monitor_status_since_dtcs_cleared FLOAT,
    hardware_status                 FLOAT,
    pidnamenotavailable             FLOAT,
    fuel_type                       FLOAT,

    -- Derived features
    driver_score                    FLOAT,
    aggressive_throttle             SMALLINT      -- 0/1
);

-- --------------------------------------------------------
-- INDEXES for common query patterns
-- --------------------------------------------------------

CREATE INDEX idx_ft_device_id  ON fleet_telematics (device_id);
CREATE INDEX idx_ft_timestamp  ON fleet_telematics (timestamp);
CREATE INDEX idx_ft_alarm      ON fleet_telematics (alarm_class);
CREATE INDEX idx_ft_device_ts  ON fleet_telematics (device_id, timestamp);

-- --------------------------------------------------------
-- RAW EVENTS TABLE (long format, preserves original data)
-- --------------------------------------------------------

DROP TABLE IF EXISTS fleet_raw_events CASCADE;

CREATE TABLE fleet_raw_events (
    id          SERIAL PRIMARY KEY,
    device_id   VARCHAR(64)   NOT NULL,
    time_mili   BIGINT,
    timestamp   TIMESTAMP     NOT NULL,
    value       TEXT,
    variable    VARCHAR(128),
    alarm_class SMALLINT      NOT NULL DEFAULT 0
);

CREATE INDEX idx_raw_device   ON fleet_raw_events (device_id);
CREATE INDEX idx_raw_ts       ON fleet_raw_events (timestamp);
CREATE INDEX idx_raw_variable ON fleet_raw_events (variable);
