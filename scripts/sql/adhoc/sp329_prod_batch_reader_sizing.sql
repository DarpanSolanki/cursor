WITH active AS (
    SELECT account_id
    FROM mfi_accounting.loan_account
    WHERE loan_status = 'ACTIVE'
),
stats AS (
    SELECT
        count(*)::bigint AS active_loan_count,
        min(account_id) AS min_account_id,
        max(account_id) AS max_account_id,
        (count(*)::bigint / 50) + 1 AS ids_per_partition_grid_50,
        (count(*)::bigint / 75) + 1 AS ids_per_partition_grid_75
    FROM active
),
gucs AS (
    SELECT
        (SELECT setting FROM pg_settings WHERE name = 'work_mem') AS work_mem_setting,
        (SELECT unit FROM pg_settings WHERE name = 'work_mem') AS work_mem_unit,
        (SELECT setting FROM pg_settings WHERE name = 'enable_nestloop') AS enable_nestloop,
        (SELECT setting FROM pg_settings WHERE name = 'yb_enable_batchednl') AS yb_enable_batchednl,
        (SELECT setting FROM pg_settings WHERE name = 'yb_prefer_bnl') AS yb_prefer_bnl,
        (SELECT setting FROM pg_settings WHERE name = 'yb_bnl_batch_size') AS yb_bnl_batch_size,
        (SELECT setting FROM pg_settings WHERE name = 'temp_file_limit') AS temp_file_limit
),
sample_part AS (
    SELECT account_id AS sample_partition_max_id_grid_50
    FROM active
    ORDER BY account_id
    OFFSET GREATEST((SELECT ids_per_partition_grid_50 FROM stats) - 1, 0)
    LIMIT 1
),
work_mem_mb AS (
    SELECT
        CASE lower(coalesce(g.work_mem_unit, 'kb'))
            WHEN 'b'  THEN g.work_mem_setting::numeric / (1024 * 1024)
            WHEN 'kb' THEN g.work_mem_setting::numeric / 1024
            WHEN 'mb' THEN g.work_mem_setting::numeric
            WHEN 'gb' THEN g.work_mem_setting::numeric * 1024
            ELSE g.work_mem_setting::numeric / 1024
        END AS mb
    FROM gucs g
)
SELECT
    current_database() AS database_name,
    g.work_mem_setting,
    g.work_mem_unit,
    round(w.mb, 2) AS work_mem_mb,
    g.enable_nestloop,
    g.yb_enable_batchednl,
    g.yb_prefer_bnl,
    g.yb_bnl_batch_size,
    g.temp_file_limit,
    s.active_loan_count,
    s.min_account_id,
    s.max_account_id,
    s.ids_per_partition_grid_50,
    s.ids_per_partition_grid_75,
    50 AS concurrent_partitions_grid_50,
    75 AS concurrent_partitions_grid_75,
    round(50 * w.mb, 1) AS approx_peak_hash_mem_mb_grid_50,
    round(75 * w.mb, 1) AS approx_peak_hash_mem_mb_grid_75,
    s.min_account_id AS sample_partition_min_id_grid_50,
    sp.sample_partition_max_id_grid_50,
    now() AS probed_at
FROM stats s
CROSS JOIN gucs g
CROSS JOIN work_mem_mb w
LEFT JOIN sample_part sp ON true;
