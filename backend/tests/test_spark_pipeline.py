from datetime import datetime

from pyspark.sql import SparkSession, Row

from pipeline.process_telemetry import summaries, transform_telemetry


def test_spark_features_and_window():
    spark = SparkSession.builder.master("local[2]").appName("safedrive-test").getOrCreate()
    try:
        rows = [Row(vehicle_id=1, timestamp=datetime(2026, 1, 1, 0, 0), speed_mph=30.0, acceleration_mps2=-3.0, steering_angle=0.0, brake_pressure=10.0, battery_percent=90.0, sensor_status="OK", route_id="R-01", software_version="sim-1.0"), Row(vehicle_id=1, timestamp=datetime(2026, 1, 1, 0, 10), speed_mph=65.0, acceleration_mps2=2.5, steering_angle=0.0, brake_pressure=10.0, battery_percent=89.0, sensor_status="DEGRADED", route_id="R-01", software_version="sim-1.0")]
        result = transform_telemetry(spark.createDataFrame(rows))
        values = result.orderBy("timestamp").collect()
        assert values[0].is_hard_braking and values[0].previous_speed_mph is None
        assert values[1].is_rapid_acceleration and values[1].is_speed_threshold and values[1].is_sensor_failure
        assert values[1].speed_change_mph == 35.0
        vehicle, route, _, _ = summaries(result)
        assert vehicle.collect()[0].telemetry_record_count == 2
        assert route.collect()[0].safety_condition_count == 2
    finally:
        spark.stop()
