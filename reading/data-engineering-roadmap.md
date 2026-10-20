# Data Engineering: Complete Learning Roadmap

> **Estimated time:** 8-14 months (beginner to job-ready)
> **Prerequisites:** Basic computer literacy, willingness to learn
> **Career relevance:** Identified as a key bottleneck skill for AI projects across all 2026 industry reports

---

## Table of Contents

1. [What is Data Engineering?](#1-what-is-data-engineering)
2. [Why Data Engineering Matters in the AI Era](#2-why-data-engineering-matters-in-the-ai-era)
3. [Roadmap Overview](#3-roadmap-overview)
4. [Phase 1: Foundations (Month 1-3)](#phase-1-foundations-month-1-3)
5. [Phase 2: Core Data Engineering (Month 3-6)](#phase-2-core-data-engineering-month-3-6)
6. [Phase 3: Cloud & Distributed Systems (Month 6-9)](#phase-3-cloud--distributed-systems-month-6-9)
7. [Phase 4: Advanced & AI-Era Skills (Month 9-12)](#phase-4-advanced--ai-era-skills-month-9-12)
8. [Phase 5: Specialization & Portfolio (Month 12-14)](#phase-5-specialization--portfolio-month-12-14)
9. [Tools & Technologies Reference](#tools--technologies-reference)
10. [Project Ideas by Phase](#project-ideas-by-phase)
11. [Career Paths & Salary Expectations](#career-paths--salary-expectations)
12. [Resources & Learning Platforms](#resources--learning-platforms)

---

## 1. What is Data Engineering?

Data engineering is the discipline of designing, building, and maintaining the systems that collect, store, transform, and deliver data so that analysts, data scientists, and AI/ML systems can use it reliably.

**A data engineer's core responsibilities:**
- Building and maintaining data pipelines (ETL/ELT)
- Designing data models and schemas
- Ensuring data quality, reliability, and freshness
- Managing data infrastructure (databases, warehouses, lakes)
- Optimizing performance and cost of data systems
- Enabling downstream consumers (analysts, ML engineers, AI agents)

**Data Engineering vs. Related Roles:**

| Role | Focus | Analogy |
|------|-------|---------|
| **Data Engineer** | Build and maintain the plumbing | The plumber who builds the water system |
| **Data Analyst** | Query and interpret data for decisions | The person who drinks the water and reports on quality |
| **Data Scientist** | Build statistical/ML models | The chemist who tests and improves the water |
| **ML Engineer** | Deploy and serve ML models in production | The factory manager who bottles and distributes |
| **Analytics Engineer** | Transform raw data into clean models for analysts | The water treatment specialist |

---

## 2. Why Data Engineering Matters in the AI Era

From our AI trends research, data engineering emerges as a critical bottleneck:

- **51% of AI project failures** trace back to data quality issues, not model issues
- **RAG, fine-tuning, and agentic AI** all depend on clean, well-structured, accessible data
- **AI agents need reliable data pipelines** to function autonomously
- **Regulatory compliance** (EU AI Act) requires data lineage and governance
- **71% of AI job postings** require Python; nearly all require SQL -- both are data engineering foundations
- Data engineering roles carry a **28-56% wage premium** over comparable non-AI roles

> "The bottleneck for most AI projects isn't the model -- it's the data." -- Cited across multiple 2026 industry reports

---

## 3. Roadmap Overview

```
Month:  1----2----3----4----5----6----7----8----9----10---11---12---13---14
        |=========|=========|=========|=========|=========|=========|===|
Phase:  |  1. FOUNDATIONS   | 2. CORE DATA ENG  | 3. CLOUD/DISTRIB  |4/5|
        |                   |                    |                   |   |
        | SQL               | ETL/ELT Pipelines  | Cloud Platform    |ADV|
        | Python            | Data Warehousing   | Spark/Distributed |   |
        | Linux/CLI         | Orchestration      | Streaming         |SPE|
        | Git               | Data Modeling      | IaC/Containers    |   |
        | Database Basics   | dbt                | Monitoring        |PRT|
```

---

## Phase 1: Foundations (Month 1-3)

### 1.1 SQL (The Most Critical Skill)

SQL is the single most important skill for a data engineer. It appears in virtually every job posting and is the primary interface to production data.

**What to learn:**

| Topic | Details | Priority |
|-------|---------|----------|
| Basic queries | SELECT, WHERE, ORDER BY, LIMIT | Week 1 |
| Filtering & sorting | AND, OR, IN, BETWEEN, LIKE, IS NULL | Week 1 |
| Aggregations | GROUP BY, HAVING, COUNT, SUM, AVG, MIN, MAX | Week 2 |
| Joins | INNER, LEFT, RIGHT, FULL OUTER, CROSS, self-joins | Week 2-3 |
| Subqueries | Scalar, correlated, EXISTS, IN with subqueries | Week 3 |
| Window functions | ROW_NUMBER, RANK, LAG, LEAD, running totals, partitions | Week 4 |
| CTEs | WITH clause, recursive CTEs | Week 4 |
| DDL | CREATE, ALTER, DROP, constraints, indexes | Week 5 |
| DML | INSERT, UPDATE, DELETE, MERGE/UPSERT | Week 5 |
| Performance | EXPLAIN plans, indexing strategies, query optimization | Week 6 |
| Advanced | Pivoting, stored procedures, materialized views, temp tables | Week 7-8 |

**Practice databases:** PostgreSQL (recommended first choice) or MySQL.

**Practice platforms:**
- LeetCode (SQL problems)
- HackerRank (SQL challenges)
- SQLZoo (interactive tutorials)
- Mode Analytics SQL tutorial

**Milestone:** Write a complex analytical query with multiple joins, window functions, and CTEs that answers a real business question.

---

### 1.2 Python for Data Engineering

Python is not used here for data science or ML, but specifically for data engineering tasks: scripting, automation, API interaction, and data manipulation.

**What to learn:**

| Topic | Details | Priority |
|-------|---------|----------|
| Core syntax | Variables, types, control flow, functions, classes | Week 1-2 |
| Data structures | Lists, dicts, sets, tuples, comprehensions | Week 2 |
| File I/O | Reading/writing CSV, JSON, Parquet, YAML | Week 3 |
| Error handling | try/except, custom exceptions, logging | Week 3 |
| Libraries: pandas | DataFrames, read_csv, merge, groupby, apply | Week 4-5 |
| Libraries: requests | API calls, authentication, pagination, error handling | Week 5 |
| Libraries: sqlalchemy | Database connections, ORM basics, raw SQL execution | Week 6 |
| Testing | pytest, unit tests, fixtures, mocking | Week 6 |
| Virtual environments | venv, pip, requirements.txt, pyproject.toml | Week 7 |
| Scripting patterns | CLI scripts with argparse, scheduling, config files | Week 7-8 |

**Key principle:** Write clean, testable, well-structured Python. Data pipelines must be reliable and maintainable, not just functional.

**Milestone:** Build a Python script that extracts data from a REST API, transforms it, and loads it into a PostgreSQL database.

---

### 1.3 Linux, CLI, and Shell Basics

Most data infrastructure runs on Linux. You need to be comfortable on the command line.

**What to learn:**

| Topic | Details |
|-------|---------|
| Navigation | cd, ls, pwd, find, tree |
| File operations | cp, mv, rm, mkdir, chmod, chown |
| Text processing | grep, awk, sed, sort, uniq, wc, head, tail, cut |
| Piping & redirection | \|, >, >>, 2>&1, tee |
| Process management | ps, top, kill, nohup, & (background) |
| SSH | ssh, scp, ssh-keygen, config |
| Bash scripting | Variables, loops, conditionals, functions, cron |
| Package management | apt/yum, systemctl |

**Milestone:** Write a bash script that automates a daily data backup with logging and error notification.

---

### 1.4 Git and Version Control

Every data pipeline lives in version control.

**What to learn:**
- Core workflow: init, add, commit, push, pull, clone
- Branching: branch, checkout, merge, rebase
- Collaboration: pull requests, code review, conflict resolution
- Best practices: meaningful commit messages, .gitignore, branch naming conventions
- GitHub/GitLab: issues, CI/CD basics

**Milestone:** Contribute to a collaborative project with branching, pull requests, and conflict resolution.

---

### 1.5 Database Fundamentals

**Relational databases (start here):**
- PostgreSQL (recommended): most versatile, widely used
- Concepts: tables, rows, columns, primary/foreign keys, constraints, normalization (1NF-3NF), ACID properties, transactions, indexes (B-tree, hash), views

**NoSQL databases (awareness level):**

| Type | Examples | When to Use |
|------|----------|-------------|
| Document | MongoDB, DynamoDB | Flexible schemas, nested data |
| Key-Value | Redis, DynamoDB | Caching, sessions, simple lookups |
| Column-Family | Cassandra, HBase | Time-series, high write throughput |
| Graph | Neo4j, Neptune | Relationship-heavy data |

**Milestone:** Design a normalized database schema for a real-world scenario (e.g., e-commerce), create it in PostgreSQL, populate it, and write analytical queries.

---

## Phase 2: Core Data Engineering (Month 3-6)

### 2.1 ETL/ELT Pipelines

The bread and butter of data engineering.

**Concepts:**

| Concept | ETL | ELT |
|---------|-----|-----|
| **Process** | Extract -> Transform -> Load | Extract -> Load -> Transform |
| **Where transformation happens** | Before loading (staging server) | After loading (in the warehouse) |
| **Best for** | Structured data, compliance | Large volumes, cloud warehouses |
| **Modern trend** | Legacy but still used | Dominant in modern stacks |

**What to learn:**
- Extract: APIs, databases, files (CSV, JSON, Parquet, Avro), web scraping, CDC (Change Data Capture)
- Transform: Cleaning, deduplication, type casting, joining, aggregating, enriching
- Load: Batch inserts, upserts, incremental loads, full refreshes
- Patterns: Idempotency (re-running won't duplicate data), backfill, retry logic, dead letter queues
- Quality: Schema validation, row counts, null checks, freshness checks

**Milestone:** Build an end-to-end ELT pipeline that extracts from multiple sources, loads to a warehouse, and transforms with tests.

---

### 2.2 Data Warehousing

**Core concepts:**

| Concept | Description |
|---------|-------------|
| **Dimensional modeling** | Star schema, snowflake schema, fact and dimension tables |
| **Slowly Changing Dimensions (SCD)** | Type 1 (overwrite), Type 2 (history tracking), Type 3 (previous value column) |
| **Grain** | The level of detail in a fact table (e.g., one row per order line item) |
| **Surrogate keys** | System-generated keys that decouple warehouse from source systems |
| **Partitioning** | Splitting tables by date, region, etc. for query performance |
| **Clustering** | Sorting data within partitions for scan efficiency |

**Warehouse platforms to learn (pick one):**

| Platform | Strengths | Good For |
|----------|-----------|----------|
| **BigQuery** (Google) | Serverless, fast SQL, easy to start | Beginners, Google Cloud users |
| **Snowflake** | Multi-cloud, separation of storage/compute | Enterprise, multi-cloud |
| **Redshift** (AWS) | Deep AWS integration, mature | AWS-heavy organizations |
| **DuckDB** | Local/embedded, fast analytics, free | Learning, prototyping, small-medium data |

**Milestone:** Design a star schema for a business domain, implement it in a warehouse, and build analytical views.

---

### 2.3 Data Orchestration

Orchestrators schedule and coordinate pipeline tasks, handling dependencies, retries, and alerts.

**Tools to learn:**

| Tool | Status | Notes |
|------|--------|-------|
| **Apache Airflow** | Industry standard | DAGs in Python, huge ecosystem, most job postings mention it |
| **Dagster** | Rising fast | Software-defined assets, better testing, modern DX |
| **Prefect** | Modern alternative | Python-native, good for smaller teams |
| **Mage** | Newer option | Visual + code hybrid |

**Start with Airflow** (most jobs require it), then explore Dagster (increasingly preferred for new projects).

**What to learn:**
- DAG (Directed Acyclic Graph) concepts
- Task dependencies and triggers
- Scheduling (cron expressions)
- Error handling and retries
- Alerting and monitoring
- Variables, connections, and secrets management
- Sensors (wait for external events)
- Dynamic task generation
- Testing DAGs locally

**Milestone:** Build an Airflow DAG that orchestrates a multi-step pipeline with error handling, retries, and Slack alerts.

---

### 2.4 dbt (Data Build Tool)

dbt is the standard tool for the "T" in ELT -- transforming data already loaded in a warehouse.

**What to learn:**

| Topic | Details |
|-------|---------|
| Models | SQL SELECT statements that dbt materializes as tables/views |
| Materializations | View, table, incremental, ephemeral |
| refs and sources | Dependency management between models |
| Tests | Built-in (unique, not_null, accepted_values, relationships) and custom |
| Documentation | Auto-generated docs from YAML and descriptions |
| Macros | Jinja-templated SQL for reusable logic |
| Seeds | CSV files loaded into the warehouse |
| Snapshots | SCD Type 2 tracking |
| Packages | Reusable dbt modules (dbt-utils, dbt-expectations) |

**Milestone:** Build a dbt project with staging, intermediate, and mart layers, complete with tests and documentation.

---

### 2.5 Data Formats and Serialization

| Format | Type | Strengths | Use Case |
|--------|------|-----------|----------|
| **CSV** | Row-based text | Human-readable, universal | Small data exchange |
| **JSON** | Nested text | Flexible schema, API standard | API responses, configs |
| **Parquet** | Columnar binary | Compressed, fast analytics, schema embedded | Data lakes, analytics |
| **Avro** | Row-based binary | Schema evolution, compact | Streaming, Kafka |
| **ORC** | Columnar binary | Hive-optimized, good compression | Hadoop ecosystem |
| **Delta Lake** | Parquet + transaction log | ACID on data lakes, time travel | Lakehouse architecture |
| **Iceberg** | Table format | Open standard, multi-engine | Modern lakehouse |

**Key takeaway:** Learn Parquet deeply -- it's the dominant format for modern data engineering. Understand when to choose row-based vs. columnar formats.

---

## Phase 3: Cloud & Distributed Systems (Month 6-9)

### 3.1 Cloud Platform (Pick One to Start)

| Platform | Key Data Services | Market Share |
|----------|-------------------|-------------|
| **AWS** | S3, Glue, Redshift, EMR, Kinesis, Lambda, Step Functions | Largest |
| **GCP** | GCS, BigQuery, Dataflow, Dataproc, Pub/Sub, Cloud Functions | Strong in data/ML |
| **Azure** | Blob Storage, Synapse, Data Factory, Databricks, Event Hubs | Enterprise-heavy |

**What to learn on any platform:**
- Object storage (S3 / GCS / Blob) -- the foundation of data lakes
- IAM (Identity and Access Management) -- security basics
- Networking basics -- VPCs, subnets, firewalls
- Serverless compute -- Lambda / Cloud Functions
- Managed databases -- RDS / Cloud SQL
- Data warehouse -- Redshift / BigQuery / Synapse
- Cost management -- budgets, alerts, reserved instances

**Recommendation:** Start with **GCP + BigQuery** (easiest learning curve, generous free tier) or **AWS** (most job postings).

**Milestone:** Deploy a complete data pipeline on a cloud platform: ingest from API -> store in object storage -> transform in warehouse -> serve via dashboard.

---

### 3.2 Apache Spark and Distributed Computing

When data exceeds what a single machine can handle, you need distributed processing.

**What to learn:**

| Topic | Details |
|-------|---------|
| Core concepts | Driver, executors, partitions, shuffles, lazy evaluation |
| RDDs | Low-level API (understand conceptually) |
| DataFrames | Primary API for structured data processing |
| Spark SQL | SQL on distributed data |
| Transformations vs. Actions | Lazy vs. eager operations |
| Joins | Broadcast joins, sort-merge joins, skew handling |
| Performance tuning | Partition count, caching, broadcast variables, AQE |
| PySpark | Python API for Spark (most common for data engineers) |
| Spark on cloud | EMR (AWS), Dataproc (GCP), Databricks (multi-cloud) |

**When Spark is needed:**
- Data volumes in the tens of GB to PB range
- Complex transformations on large datasets
- Batch processing of data lake contents
- Feature engineering at scale for ML

**When Spark is overkill:**
- Data fits in memory (use pandas or DuckDB instead)
- Simple SQL transformations (use dbt + warehouse)
- Real-time streaming of small volumes (use lighter tools)

**Milestone:** Process a multi-GB dataset with PySpark: read from a data lake, perform complex transformations, and write optimized Parquet output.

---

### 3.3 Streaming and Real-Time Data

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **Apache Kafka** | Distributed event streaming platform | High-throughput, event-driven architectures |
| **Apache Flink** | Stream processing engine | Complex event processing, low-latency |
| **Spark Structured Streaming** | Micro-batch streaming on Spark | When you already use Spark |
| **AWS Kinesis / GCP Pub/Sub** | Managed streaming | Cloud-native, simpler setup |

**Core streaming concepts:**
- Event-driven architecture vs. batch
- Producers and consumers
- Topics, partitions, offsets (Kafka)
- At-least-once, at-most-once, exactly-once delivery
- Windowing: tumbling, sliding, session windows
- Late-arriving data and watermarks
- Stream-table joins

**Milestone:** Build a streaming pipeline with Kafka that ingests events, processes them in near-real-time, and updates a dashboard.

---

### 3.4 Containers and Infrastructure as Code

**Docker:**
- Dockerfiles: building images for pipeline components
- docker-compose: multi-container local environments
- Volumes, networks, environment variables
- Container registries (Docker Hub, ECR, GCR)

**Kubernetes (awareness level):**
- Pods, deployments, services
- Why it matters for scaling data pipelines
- Managed K8s: EKS, GKE, AKS

**Infrastructure as Code:**

| Tool | Purpose |
|------|---------|
| **Terraform** | Cloud infrastructure provisioning (most popular) |
| **Pulumi** | IaC with real programming languages |
| **CloudFormation** | AWS-specific IaC |

**Milestone:** Containerize a data pipeline with Docker, deploy it using docker-compose, and provision the cloud infrastructure with Terraform.

---

## Phase 4: Advanced & AI-Era Skills (Month 9-12)

### 4.1 Data Quality and Observability

Data quality is what separates a junior from a senior data engineer.

**Data quality dimensions:**

| Dimension | Question It Answers |
|-----------|-------------------|
| Completeness | Are there missing values or records? |
| Accuracy | Does the data reflect reality? |
| Consistency | Do related tables agree with each other? |
| Timeliness | Is the data fresh enough for its use case? |
| Uniqueness | Are there duplicates? |
| Validity | Does the data conform to expected formats and ranges? |

**Tools:**

| Tool | Focus |
|------|-------|
| **Great Expectations** | Data validation and testing framework |
| **Soda** | Data quality checks with SQL-like syntax |
| **dbt tests** | Built into dbt workflow |
| **Monte Carlo** | Data observability platform (commercial) |
| **Elementary** | Open-source dbt-native data observability |

**What to implement:**
- Schema validation at ingestion
- Row count and freshness monitoring
- Anomaly detection on key metrics
- Data lineage tracking
- Alerting on quality failures
- SLAs/SLOs for data freshness and completeness

---

### 4.2 Data Governance and Security

Increasingly important with AI regulation (EU AI Act, NIST AI RMF).

**What to learn:**

| Topic | Details |
|-------|---------|
| Access control | Role-based access (RBAC), column/row-level security |
| Encryption | At rest (AES-256), in transit (TLS), key management |
| Data masking | PII anonymization, tokenization |
| Data lineage | Tracking data from source to consumption |
| Data catalog | Metadata management, discoverability |
| Compliance | GDPR, CCPA, HIPAA basics, AI Act data requirements |
| Audit logging | Who accessed what, when, why |

**Tools:**

| Tool | Purpose |
|------|---------|
| **Apache Atlas** | Data governance and metadata (open source) |
| **DataHub** (LinkedIn) | Data catalog and lineage (open source) |
| **OpenMetadata** | Data catalog and lineage (open source) |
| **Collibra / Alation** | Enterprise data governance (commercial) |

---

### 4.3 Data Engineering for AI/ML

This is where data engineering intersects with the AI trends we researched.

**What to learn:**

| Topic | Why It Matters for AI |
|-------|----------------------|
| **Feature stores** | Centralized, versioned feature management for ML models |
| **Vector databases** | Store embeddings for RAG and similarity search (Pinecone, Weaviate, pgvector, Qdrant, Milvus) |
| **Data pipelines for LLMs** | Document ingestion, chunking, embedding generation, index updates |
| **RAG data pipelines** | Keeping retrieval indexes fresh with new data |
| **Synthetic data generation** | Generating training data when real data is scarce or sensitive |
| **Data versioning** | DVC, LakeFS -- tracking dataset versions for reproducibility |
| **ML metadata tracking** | MLflow, Weights & Biases -- experiment tracking |

**Feature stores:**

| Tool | Type |
|------|------|
| **Feast** | Open-source, offline + online serving |
| **Tecton** | Commercial, real-time features |
| **Hopsworks** | Open-source + commercial |

**This is where the highest demand is in 2026:** Data engineers who can build pipelines that feed AI systems (RAG, agents, fine-tuning) command top salaries.

---

### 4.4 DataOps and CI/CD for Data

**Principles:**
- Treat pipeline code like software: version control, testing, code review
- Automated testing: unit tests for transformations, integration tests for pipelines
- CI/CD: automated deployment of pipeline changes
- Monitoring and alerting in production
- Rollback capabilities

**CI/CD pipeline for data:**

```
Code change -> Lint/Format -> Unit tests -> Integration tests -> Deploy to staging
-> Data quality checks on staging -> Deploy to production -> Monitor
```

**Tools:**
- GitHub Actions / GitLab CI / Jenkins for CI/CD
- Pre-commit hooks for linting
- pytest for Python pipeline tests
- dbt test for transformation tests
- Great Expectations for data validation in CI

---

## Phase 5: Specialization & Portfolio (Month 12-14)

### 5.1 Choose a Specialization Track

| Track | Focus | Tools to Deepen |
|-------|-------|-----------------|
| **Analytics Engineering** | Business-facing data models and metrics | dbt, Looker/Metabase, Semantic layers |
| **ML/AI Data Engineering** | Pipelines feeding ML systems | Feature stores, vector DBs, MLflow |
| **Real-Time/Streaming** | Event-driven architectures | Kafka, Flink, real-time dashboards |
| **Platform Engineering** | Internal data platform for teams | Kubernetes, Terraform, self-serve tools |
| **Data Governance** | Compliance, security, lineage | Catalogs, lineage tools, policy engines |

### 5.2 Build Your Portfolio

**Recommended projects (build 2-4):**

| Project | Skills Demonstrated |
|---------|-------------------|
| **Batch ETL Pipeline** | Python, PostgreSQL, Airflow, Docker, dbt, data quality tests |
| **Streaming Pipeline** | Kafka, Python consumer, real-time transformations, dashboard |
| **Cloud Data Lake** | S3/GCS, Spark, Parquet, Delta/Iceberg, Terraform |
| **RAG Data Pipeline** | Document ingestion, chunking, embedding, vector DB, freshness updates |
| **Data Platform** | End-to-end: ingestion, warehouse, transformations, dashboards, monitoring |

**For each project, include:**
- Clear README with architecture diagram
- Well-structured code with tests
- Docker/docker-compose for local reproduction
- CI/CD pipeline
- Data quality checks
- Documentation of design decisions

---

## Tools & Technologies Reference

### The Modern Data Stack (2026)

```
                        +-----------------------+
                        |     CONSUMPTION       |
                        | Looker, Metabase,     |
                        | Streamlit, Jupyter,   |
                        | AI/ML Systems, LLMs   |
                        +----------+------------+
                                   |
                        +----------+------------+
                        |    TRANSFORMATION      |
                        | dbt, Spark, Python     |
                        +----------+------------+
                                   |
                        +----------+------------+
                        |      STORAGE           |
                        | Snowflake, BigQuery,   |
                        | Delta Lake, Iceberg    |
                        +----------+------------+
                                   |
                        +----------+------------+
                        |    ORCHESTRATION       |
                        | Airflow, Dagster,      |
                        | Prefect                |
                        +----------+------------+
                                   |
                        +----------+------------+
                        |     INGESTION          |
                        | Fivetran, Airbyte,     |
                        | Custom Python, CDC     |
                        +----------+------------+
                                   |
                        +----------+------------+
                        |      SOURCES           |
                        | Databases, APIs, Files,|
                        | Events, IoT, Streams   |
                        +-----------------------+
```

### Tool Popularity in Job Postings (2026)

| Tool | Mention Rate | Category |
|------|-------------|----------|
| SQL | ~95% | Query language |
| Python | ~85% | Programming |
| Airflow | ~55% | Orchestration |
| Spark | ~50% | Distributed processing |
| AWS | ~50% | Cloud |
| dbt | ~40% | Transformation |
| Kafka | ~35% | Streaming |
| Docker | ~35% | Containers |
| Snowflake | ~30% | Warehouse |
| Terraform | ~25% | IaC |
| GCP | ~25% | Cloud |
| Kubernetes | ~20% | Container orchestration |

---

## Career Paths & Salary Expectations

### Career Progression

```
Junior Data Engineer (0-2 years)
    |
    v
Data Engineer (2-4 years)
    |
    v
Senior Data Engineer (4-7 years)
    |
    +---> Staff Data Engineer (7+ years, IC track)
    |
    +---> Data Engineering Manager (7+ years, management track)
    |
    +---> Principal Data Engineer / Data Architect (10+ years)
```

### Salary Ranges (USD, 2026 estimates)

| Level | US Range | With AI/ML Skills Premium |
|-------|----------|--------------------------|
| Junior | $80K - $110K | $95K - $130K |
| Mid-level | $110K - $150K | $130K - $175K |
| Senior | $150K - $200K | $175K - $230K |
| Staff/Principal | $200K - $280K | $220K - $300K+ |

*Note: Ranges vary significantly by location, company size, and industry. AI/ML data engineering skills carry a 28-56% premium (PwC / Lightcast).*

### Related Roles to Transition Into

| From Data Engineer | To | Additional Skills Needed |
|---|---|---|
| Data Engineer | Analytics Engineer | Business acumen, BI tools, stakeholder communication |
| Data Engineer | ML Engineer | ML fundamentals, model serving, experiment tracking |
| Data Engineer | Platform Engineer | Kubernetes, internal tooling, developer experience |
| Data Engineer | Data Architect | System design, enterprise architecture, governance |
| Data Engineer | AI/ML Data Engineer | Vector DBs, feature stores, RAG pipelines, LLM ops |

---

## Resources & Learning Platforms

### Free Resources

| Resource | What It Covers |
|----------|---------------|
| [SQLBolt](https://sqlbolt.com/) | Interactive SQL lessons |
| [Mode SQL Tutorial](https://mode.com/sql-tutorial/) | SQL for analytics |
| [Python Official Tutorial](https://docs.python.org/3/tutorial/) | Python fundamentals |
| [The Missing Semester (MIT)](https://missing.csail.mit.edu/) | Linux, CLI, Git, shell scripting |
| [dbt Learn](https://courses.getdbt.com/) | Official dbt courses (free) |
| [Airflow Documentation](https://airflow.apache.org/docs/) | Official Airflow docs and tutorials |
| [Designing Data-Intensive Applications (summaries)](https://dataintensive.net/) | System design for data |

### Paid Courses / Platforms

| Platform | Best For |
|----------|----------|
| DataCamp | Structured learning paths, SQL + Python |
| Coursera (Google Data Engineering) | GCP-focused certification path |
| Udemy (various) | Affordable deep-dives on specific tools |
| Zach Wilson's Data Engineering Bootcamp | Comprehensive, project-based |
| DataExpert.io | Advanced data engineering |

### Books

| Book | Focus |
|------|-------|
| *Designing Data-Intensive Applications* (Martin Kleppmann) | **The bible.** System design fundamentals |
| *Fundamentals of Data Engineering* (Reis & Housley) | Modern data engineering overview |
| *The Data Warehouse Toolkit* (Kimball) | Dimensional modeling |
| *Data Pipelines Pocket Reference* (James Densmore) | Practical pipeline patterns |
| *Streaming Systems* (Akidau, Chernyak, Lax) | Streaming theory and practice |

### Communities

| Community | Platform |
|-----------|----------|
| r/dataengineering | Reddit |
| Data Engineering Weekly | Newsletter |
| dbt Community | Slack + Discourse |
| Seattle Data Guy | YouTube |
| Data Council | Conferences + YouTube |

---

## Weekly Study Schedule (Suggested)

For someone studying part-time (10-15 hours/week):

| Day | Activity | Duration |
|-----|----------|----------|
| Monday | Theory / reading / video lectures | 2 hours |
| Tuesday | Hands-on coding / tool practice | 2 hours |
| Wednesday | Theory / reading / video lectures | 2 hours |
| Thursday | Hands-on coding / tool practice | 2 hours |
| Friday | Project work | 2 hours |
| Saturday | Project work + review | 3 hours |
| Sunday | Rest or light review / community reading | 0-2 hours |

---

## Checklist: Am I Job-Ready?

- [ ] Can write complex SQL with joins, window functions, CTEs, and optimization
- [ ] Can build Python scripts for data extraction, transformation, and loading
- [ ] Comfortable on Linux command line
- [ ] Understand relational database design and normalization
- [ ] Can design a dimensional model (star/snowflake schema)
- [ ] Have built ETL/ELT pipelines with orchestration (Airflow or Dagster)
- [ ] Have used dbt for warehouse transformations with tests
- [ ] Understand at least one cloud platform (AWS, GCP, or Azure)
- [ ] Can work with distributed data using Spark or equivalent
- [ ] Know data formats (Parquet, Avro, JSON) and when to use each
- [ ] Can containerize pipelines with Docker
- [ ] Understand data quality, testing, and observability
- [ ] Have 2-4 portfolio projects on GitHub
- [ ] Can discuss data modeling, pipeline design, and tradeoffs in an interview

---

*Roadmap compiled from industry reports, job posting analysis, and community best practices as of October 2026.*

## Sources

- [DataQuest - Data Engineer Roadmap for Beginners](https://www.dataquest.io/blog/the-data-engineer-roadmap-for-beginners/)
- [Data Engineer Academy - Career Roadmap 2026](https://dataengineeracademy.com/blog/data-engineer-career-roadmap-for-2026-skills-stack-and-growth/)
- [Scaler - Ultimate AI Data Engineer Roadmap 2026](https://www.scaler.com/blog/data-engineer-roadmap/)
- [LearnSoft - Data Engineering Roadmap 2026](https://www.learnsoft.org/blog/data-engineering-roadmap-2026)
- [Futurense - Data Engineer Roadmap](https://futurense.com/blog/data-engineer-roadmap)
- [TripleTen - AI Skills to Learn in 2026](https://tripleten.com/blog/posts/ai-skills)
- [Innowise - AI Trends 2026](https://innowise.com/blog/ai-trends/)
