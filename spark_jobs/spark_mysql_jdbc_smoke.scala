import java.sql.Timestamp
import java.util.Properties

import spark.implicits._

case class PlatformSummary(
  run_id: String,
  creator_id: String,
  platform: String,
  total_views: Long,
  new_followers: Long,
  video_count: Int,
  conversion_rate: BigDecimal,
  calculated_at: Timestamp
)

try {
  val jdbcUrl = sys.env.getOrElse(
    "SPARK_MYSQL_JDBC_URL",
    throw new IllegalArgumentException("SPARK_MYSQL_JDBC_URL is required")
  )
  val jdbcUser = sys.env.getOrElse(
    "SPARK_MYSQL_USER",
    throw new IllegalArgumentException("SPARK_MYSQL_USER is required")
  )
  val jdbcPassword = sys.env.getOrElse(
    "SPARK_MYSQL_PASSWORD",
    throw new IllegalArgumentException("SPARK_MYSQL_PASSWORD is required")
  )
  val jdbcDriver = sys.env.getOrElse("SPARK_MYSQL_DRIVER", "com.mysql.cj.jdbc.Driver")
  val runId = sys.env.getOrElse("CREATORPULSE_SPARK_RUN_ID", s"spark_jdbc_smoke_${System.currentTimeMillis}")

  val connectionProps = new Properties()
  connectionProps.put("user", jdbcUser)
  connectionProps.put("password", jdbcPassword)
  connectionProps.put("driver", jdbcDriver)

  val calculatedAt = new Timestamp(System.currentTimeMillis)
  val rows = Seq(
    PlatformSummary(runId, "creator_003", "DOUYIN", 128986L, 15L, 1, BigDecimal("0.000116"), calculatedAt),
    PlatformSummary(runId, "creator_003", "BILIBILI", 86617L, 15L, 1, BigDecimal("0.000173"), calculatedAt),
    PlatformSummary(runId, "creator_003", "XIAOHONGSHU", 64523L, 3L, 1, BigDecimal("0.000046"), calculatedAt)
  ).toDF()

  rows.write.mode("append").jdbc(jdbcUrl, "spark_platform_metric_summaries", connectionProps)

  val writtenCount = spark.read.jdbc(jdbcUrl, "spark_platform_metric_summaries", connectionProps).where($"run_id" === runId).count()

  if (writtenCount != 3L) {
    throw new IllegalStateException(s"Expected 3 smoke rows, got $writtenCount")
  }

  println(s"CREATORPULSE_SPARK_JDBC_SMOKE_OK run_id=$runId rows=$writtenCount")
  System.exit(0)
} catch {
  case error: Throwable =>
    error.printStackTrace()
    System.exit(1)
}
