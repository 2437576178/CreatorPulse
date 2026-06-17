# CreatorPulse Kafka Connectivity

This folder covers roadmap phase seven: verify Windows -> VM Kafka reachability without coupling Kafka to Flask, Vue, MySQL, or Spark.

## Configure

Copy `.env.example` to `.env` and fill:

```env
KAFKA_BOOTSTRAP_SERVERS=your-vm-ip:9092
KAFKA_TEST_TIMEOUT_SECONDS=5
```

## Check TCP Connectivity

```powershell
python kafka_tools\check_connectivity.py
```

You can also pass the server directly:

```powershell
python kafka_tools\check_connectivity.py --bootstrap-servers 192.168.56.10:9092
```

If this fails, check VM IP, firewall, Kafka port, and Kafka `advertised.listeners`.

Producer / consumer tests belong after this TCP check passes.

## Build Mock Events

Before real Kafka producer / consumer is enabled, build local NDJSON events:

```powershell
python kafka_tools\mock_producer.py
```

This writes `kafka_tools/out/mock_events.ndjson` and validates the message contract.

After Kafka TCP connectivity passes and `kafka-python` is installed, the same
script can produce events:

```powershell
python kafka_tools\mock_producer.py --execute-kafka
```

## Validate Consumed Events

Validate local NDJSON output:

```powershell
python kafka_tools\mock_consumer.py
```

After Kafka TCP connectivity passes and events have been produced to Kafka:

```powershell
python kafka_tools\mock_consumer.py --execute-kafka
```

## Closed-Loop Check

Run the local closed-loop check without touching VM Kafka:

```powershell
python kafka_tools\run_closed_loop.py
```

This performs:

```text
mock data -> NDJSON producer -> NDJSON consumer validation -> offline Spark-style aggregation
```

After Kafka TCP connectivity passes and events can be produced/consumed:

```powershell
python kafka_tools\run_closed_loop.py --execute-kafka
```

The real Kafka mode is intentionally opt-in so Kafka remains decoupled from the
Flask / Vue / MySQL MVP path until the VM network is confirmed.
