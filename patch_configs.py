import re

# 1. Update run_requests.py
with open("src/models/run_requests.py", "r") as f:
    text = f.read()

new_fields = """
    book_pressure_block_z_threshold: float = 1.65
    break_even_l2_proof_book_pressure_threshold: float = 0.06
    break_even_l2_proof_imbalance_threshold: float = 0.1
    break_even_l2_proof_signed_threshold: float = 0.07
    break_even_proof_logic: str = "OR"
    ev_relaxation_enabled: bool = True
    ev_relaxation_factor: float = 0.5
    ev_relaxation_threshold: float = 10.0
    hard_l2_block_enabled: bool = True
    intraday_levels_bounce_conflict_buffer_bars: int = 2
    micro_confirmation_mode: str = "volume_delta"
    micro_confirmation_volume_delta_min_pct: float = 0.6
    signed_aggression_block_z_threshold: float = 1.65
    strategy_time_windows: Optional[Dict[str, Any]] = None
    time_of_day_filter_enabled: bool = True
    volume_profile_poc_mode: str = "favor_bounce_mean_reversion"
    weak_l2_aggression_threshold: float = 0.05
    weak_l2_break_even_min_hold_bars: int = 1
    weak_l2_fast_break_even_enabled: bool = False
"""

text = re.sub(
    r"(class StartRunRequest\(BaseModel\):.*?    run_id: str\n)",
    r"\1" + new_fields.lstrip('\n'),
    text,
    flags=re.DOTALL
)

with open("src/models/run_requests.py", "w") as f:
    f.write(text)

# 2. Update start_run_execution_config_service.py
with open("src/services/start_run_execution_config_service.py", "r") as f:
    service_text = f.read()

floats_to_add = """
    FloatPositioningSpec(
        effective_key="effective_book_pressure_block_z_threshold",
        source_key="book_pressure_block_z_threshold_source",
        request_attr="book_pressure_block_z_threshold",
        request_default=1.65,
        positioning_key="book_pressure_block_z_threshold",
        min_value=-10.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_proof_book_pressure_threshold",
        source_key="break_even_l2_proof_book_pressure_threshold_source",
        request_attr="break_even_l2_proof_book_pressure_threshold",
        request_default=0.06,
        positioning_key="break_even_l2_proof_book_pressure_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_proof_imbalance_threshold",
        source_key="break_even_l2_proof_imbalance_threshold_source",
        request_attr="break_even_l2_proof_imbalance_threshold",
        request_default=0.1,
        positioning_key="break_even_l2_proof_imbalance_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_proof_signed_threshold",
        source_key="break_even_l2_proof_signed_threshold_source",
        request_attr="break_even_l2_proof_signed_threshold",
        request_default=0.07,
        positioning_key="break_even_l2_proof_signed_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_ev_relaxation_factor",
        source_key="ev_relaxation_factor_source",
        request_attr="ev_relaxation_factor",
        request_default=0.5,
        positioning_key="ev_relaxation_factor",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_ev_relaxation_threshold",
        source_key="ev_relaxation_threshold_source",
        request_attr="ev_relaxation_threshold",
        request_default=10.0,
        positioning_key="ev_relaxation_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_micro_confirmation_volume_delta_min_pct",
        source_key="micro_confirmation_volume_delta_min_pct_source",
        request_attr="micro_confirmation_volume_delta_min_pct",
        request_default=0.6,
        positioning_key="micro_confirmation_volume_delta_min_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_signed_aggression_block_z_threshold",
        source_key="signed_aggression_block_z_threshold_source",
        request_attr="signed_aggression_block_z_threshold",
        request_default=1.65,
        positioning_key="signed_aggression_block_z_threshold",
        min_value=-10.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_weak_l2_aggression_threshold",
        source_key="weak_l2_aggression_threshold_source",
        request_attr="weak_l2_aggression_threshold",
        request_default=0.05,
        positioning_key="weak_l2_aggression_threshold",
        min_value=0.0,
    ),"""

ints_to_add = """
    IntPositioningSpec(
        effective_key="effective_intraday_levels_bounce_conflict_buffer_bars",
        source_key="intraday_levels_bounce_conflict_buffer_bars_source",
        request_attr="intraday_levels_bounce_conflict_buffer_bars",
        request_default=2,
        positioning_key="intraday_levels_bounce_conflict_buffer_bars",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_weak_l2_break_even_min_hold_bars",
        source_key="weak_l2_break_even_min_hold_bars_source",
        request_attr="weak_l2_break_even_min_hold_bars",
        request_default=1,
        positioning_key="weak_l2_break_even_min_hold_bars",
        min_value=0,
    ),"""

bools_to_add = """
    BoolPositioningSpec(
        effective_key="effective_ev_relaxation_enabled",
        source_key="ev_relaxation_enabled_source",
        request_attr="ev_relaxation_enabled",
        request_default=True,
        positioning_key="ev_relaxation_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_hard_l2_block_enabled",
        source_key="hard_l2_block_enabled_source",
        request_attr="hard_l2_block_enabled",
        request_default=True,
        positioning_key="hard_l2_block_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_time_of_day_filter_enabled",
        source_key="time_of_day_filter_enabled_source",
        request_attr="time_of_day_filter_enabled",
        request_default=True,
        positioning_key="time_of_day_filter_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_weak_l2_fast_break_even_enabled",
        source_key="weak_l2_fast_break_even_enabled_source",
        request_attr="weak_l2_fast_break_even_enabled",
        request_default=False,
        positioning_key="weak_l2_fast_break_even_enabled",
    ),"""

strs_to_add = """
    StringPositioningSpec(
        effective_key="effective_break_even_proof_logic",
        source_key="break_even_proof_logic_source",
        request_attr="break_even_proof_logic",
        request_default="OR",
        positioning_key="break_even_proof_logic",
    ),
    StringPositioningSpec(
        effective_key="effective_micro_confirmation_mode",
        source_key="micro_confirmation_mode_source",
        request_attr="micro_confirmation_mode",
        request_default="volume_delta",
        positioning_key="micro_confirmation_mode",
    ),
    StringPositioningSpec(
        effective_key="effective_volume_profile_poc_mode",
        source_key="volume_profile_poc_mode_source",
        request_attr="volume_profile_poc_mode",
        request_default="favor_bounce_mean_reversion",
        positioning_key="volume_profile_poc_mode",
    ),"""

service_text = re.sub(
    r"(_FLOAT_POSITIONING_SPECS: tuple\[FloatPositioningSpec, \.\.\.\] = \(\n)",
    r"\1" + floats_to_add.lstrip('\n'),
    service_text,
    flags=re.DOTALL
)

service_text = re.sub(
    r"(_INT_POSITIONING_SPECS: tuple\[IntPositioningSpec, \.\.\.\] = \(\n)",
    r"\1" + ints_to_add.lstrip('\n'),
    service_text,
    flags=re.DOTALL
)

service_text = re.sub(
    r"(_BOOL_POSITIONING_SPECS: tuple\[BoolPositioningSpec, \.\.\.\] = \(\n)",
    r"\1" + bools_to_add.lstrip('\n'),
    service_text,
    flags=re.DOTALL
)

service_text = re.sub(
    r"(_STRING_POSITIONING_SPECS: tuple\[StringPositioningSpec, \.\.\.\] = \(\n)",
    r"\1" + strs_to_add.lstrip('\n'),
    service_text,
    flags=re.DOTALL
)

with open("src/services/start_run_execution_config_service.py", "w") as f:
    f.write(service_text)
print("Files patched successfully")
