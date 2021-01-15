# from cbc_file_paths import *

from pathlib import Path

# Base Path
base_path = Path.cwd()

# Data paths
data_path = base_path / 'data'
cache_path = base_path / 'cache'

# Can Override
local_parameters_path = base_path / 'parameters' / 'Local'
system_parameters_path = base_path / 'parameters' / 'System'

kml_path = local_parameters_path / 'KML'

system_translations_path = system_parameters_path
system_translations_name_base = 'SystemTranslations'

# Input paths
inputs_path = base_path / 'Inputs'
inputs_parse_path = inputs_path / 'Parse'
inputs_email_path = inputs_path / 'EmailToContacts'
inputs_merge_path = inputs_path / 'Merge'
inputs_count_path = inputs_path / 'Count'

# - Service-Parse
# - Service-EmailToContacts
# - Service-ProcessEBird
# - Service-Weather
# - Service-RareBird
# - Service-Merge


raw_data_path = data_path / 'raw'
interim_data_path = data_path / 'interim'
processed_data_path = data_path / 'processed'
external_data_path = data_path / 'external'
reference_path = base_path / 'reference'

# Reports paths
reports_path = base_path / 'reports'
figures_path = reports_path / 'figures'
reports_setup_path = reports_path / 'setup'
reports_debug_path = reports_path / 'debug'

rare_bird_output_path = reports_path / 'rare-bird-forms'

#################
translations_path = reports_path / 'PossibleLocalTranslations.csv'
translations_xl_path = reports_path / 'PossibleLocalTranslations.xlsx'
#################


# HTML construction paths
html_base_path = base_path / 'xexperiments' / 'html_templates'
html_path_pre_table_1 = html_base_path / 'pre-table1-p1.html'
html_path_between_tables = html_base_path / 'between-tables.html'
html_path_post_table_2 = html_base_path / 'post-table2-p1.html'

html_path_participants_pre_table = html_base_path / 'participants_pre_table.html'
html_path_participants_post_table = html_base_path / 'participants_post_table.html'

# Outputs paths
outputs_path = base_path / 'Outputs'

daily_counts_path = reports_path / 'daily_counts.csv'
daily_checklists_path = reports_path / 'daily_checklists.csv'
html_path_name_fmt = 'tally_sheet_p{0}.html'
html_path_output_dir = reports_path
checklist_filers_path = reports_path / 'all_checklist_filers.csv'
updated_checklist_path = reports_path / 'Summary.xlsx'

debug_path = base_path / 'debug'

html_path_participants_list = reports_path / 'local_participants_list.html'
excel_path_participants_list = reports_path / 'local_participants_list.xlsx'

pdf_conversion_details_path = reports_debug_path / 'pdf-conversion-details'

final_checklist_path = reports_path / 'FinalChecklist-printable.xlsx'
local_checklist_generated_path = reports_path / 'LocalChecklist-generated.xlsx'

# Cache/Interim paths
taxonomy_cache_path = cache_path / 'taxonomy.csv'
reverse_geolocation_cache_path = cache_path / 'ReverseGeolocationCache.csv'
checklist_ratings_cache_path = cache_path / 'checklist_ratings.csv'

ebird_visits_path = cache_path / 'visits'
ebird_historic_path = cache_path / 'historic'
ebird_details_path = cache_path / 'details'

# Credentials
eBirdCredential_path = Path.home() / 'eBirdCredentials.yml'
credentials_openweather_path = Path.home() / 'credentials-openweather.yml'

# -------- Above here copied from AutomatingCBC ---------

taxonomy_path = reference_path / 'Taxonomy'
ebird_taxonomy_v2019_path = taxonomy_path / 'eBird_Taxonomy_v2019.xlsx'

ml_checklists_path = reference_path / 'MLChecklists'
test_data_path = base_path / 'tests'

samples_path = base_path / 'samples'


def create_project_paths():
    default_mode = 0o755
    # data_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    # raw_data_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    # interim_data_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    # processed_data_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    # external_data_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    reports_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    # figures_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    debug_path.mkdir(mode=default_mode, parents=False, exist_ok=True)

    # Inputs paths
    inputs_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    inputs_parse_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    inputs_email_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    inputs_merge_path.mkdir(mode=default_mode, parents=False, exist_ok=True)
    inputs_count_path.mkdir(mode=default_mode, parents=False, exist_ok=True)

    # Output path
    outputs_path.mkdir(mode=default_mode, parents=False, exist_ok=True)

    # Cache paths
    for fpath in [cache_path, ebird_visits_path, ebird_historic_path, ebird_details_path]:
        fpath.mkdir(mode=default_mode, parents=False, exist_ok=True)
