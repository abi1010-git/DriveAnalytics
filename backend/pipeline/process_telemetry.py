"""Process synthetic telemetry with PySpark and persist small summaries to PostgreSQL."""
import argparse
import os
import sys
import time
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType, TimestampType
from sqlalchemy import delete, insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base, SessionLocal, engine
from app.models import SparkRouteSummary, SparkSoftwareSummary, SparkTimeSummary, SparkVehicleSummary

INPUT_SCHEMA = StructType([
    StructField("vehicle_id", IntegerType(), False), StructField("timestamp", TimestampType(), False),
    StructField("speed_mph", DoubleType(), True), StructField("acceleration_mps2", DoubleType(), True),
    StructField("steering_angle", DoubleType(), True), StructField("brake_pressure", DoubleType(), True),
    StructField("battery_percent", DoubleType(), True), StructField("sensor_status", StringType(), True),
    StructField("route_id", StringType(), True), StructField("software_version", StringType(), True),
])


def transform_telemetry(df, hard_braking=-2.2, rapid_acceleration=2.2, speed_threshold=58.0):
    cleaned = (df.withColumn("speed_mph", F.col("speed_mph").cast("double"))
        .withColumn("acceleration_mps2", F.col("acceleration_mps2").cast("double"))
        .dropna(subset=["vehicle_id", "timestamp"])
        .fillna({"speed_mph": 0.0, "acceleration_mps2": 0.0, "sensor_status": "UNKNOWN", "route_id": "UNKNOWN", "software_version": "UNKNOWN"}))
    window = Window.partitionBy("vehicle_id").orderBy("timestamp")
    return (cleaned.withColumn("previous_speed_mph", F.lag("speed_mph").over(window))
        .withColumn("speed_change_mph", F.col("speed_mph") - F.coalesce(F.col("previous_speed_mph"), F.col("speed_mph")))
        .withColumn("absolute_acceleration", F.abs("acceleration_mps2"))
        .withColumn("is_hard_braking", F.col("acceleration_mps2") < F.lit(hard_braking))
        .withColumn("is_rapid_acceleration", F.col("acceleration_mps2") > F.lit(rapid_acceleration))
        .withColumn("is_speed_threshold", F.col("speed_mph") > F.lit(speed_threshold))
        .withColumn("is_sensor_failure", F.col("sensor_status") != F.lit("OK"))
        .withColumn("safety_condition", F.col("is_hard_braking") | F.col("is_rapid_acceleration") | F.col("is_speed_threshold") | F.col("is_sensor_failure"))
        .withColumn("telemetry_health_status", F.when(F.col("is_sensor_failure"), "DEGRADED").when(F.col("safety_condition"), "ATTENTION").otherwise("HEALTHY")))


def summaries(df):
    condition = F.col("safety_condition").cast("int")
    vehicle = df.groupBy("vehicle_id").agg(F.count("*").alias("telemetry_record_count"), F.avg("speed_mph").alias("average_speed"), F.max("speed_mph").alias("max_speed"), F.sum(F.col("is_hard_braking").cast("int")).alias("hard_braking_count"), F.sum(F.col("is_rapid_acceleration").cast("int")).alias("rapid_acceleration_count"), F.sum(F.col("is_sensor_failure").cast("int")).alias("sensor_failure_count"))
    route = df.groupBy("route_id").agg(F.count("*").alias("telemetry_record_count"), F.avg("speed_mph").alias("average_speed"), F.sum(condition).alias("safety_condition_count"))
    time_summary = df.withColumn("time_bucket", F.date_trunc("hour", "timestamp")).groupBy("time_bucket").agg(F.count("*").alias("telemetry_record_count"), F.sum(condition).alias("safety_condition_count"))
    software = df.groupBy("software_version").agg(F.count("*").alias("telemetry_count"), F.sum(condition).alias("safety_condition_count"))
    return vehicle, route, time_summary, software


def write_postgres(vehicle, route, time_summary, software):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        for model, frame in ((SparkVehicleSummary, vehicle), (SparkRouteSummary, route), (SparkTimeSummary, time_summary), (SparkSoftwareSummary, software)):
            db.execute(delete(model))
            db.execute(insert(model), [row.asDict() for row in frame.toLocalIterator()])
        db.commit()
    finally: db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/raw/telemetry"))
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    parser.add_argument("--no-postgres", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    spark = SparkSession.builder.appName("SafeDriveTelemetryPipeline").master(os.getenv("SPARK_MASTER", "local[*]")).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    raw = spark.read.schema(INPUT_SCHEMA).parquet(str(args.input))
    processed = transform_telemetry(raw)
    vehicle, route, time_summary, software = summaries(processed)
    args.output.mkdir(parents=True, exist_ok=True)
    processed.write.mode("overwrite").parquet(str(args.output / "processed_telemetry"))
    vehicle.write.mode("overwrite").parquet(str(args.output / "vehicle_summary"))
    route.write.mode("overwrite").parquet(str(args.output / "route_summary"))
    time_summary.write.mode("overwrite").parquet(str(args.output / "time_summary"))
    software.write.mode("overwrite").parquet(str(args.output / "software_summary"))
    input_count = raw.count()
    output_counts = {"processed_telemetry": processed.count(), "vehicle_summary": vehicle.count(), "route_summary": route.count(), "time_summary": time_summary.count(), "software_summary": software.count()}
    if not args.no_postgres: write_postgres(vehicle, route, time_summary, software)
    print(f"Processed {input_count} rows in {time.perf_counter() - started:.2f}s; outputs={output_counts}; postgres={'skipped' if args.no_postgres else 'loaded'}")
    spark.stop()


if __name__ == "__main__": main()
