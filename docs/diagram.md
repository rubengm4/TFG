erDiagram
%% Core Entities
USER ||--o{ USER_PROJECT : belongs_to
PROJECT ||--o{ USER_PROJECT : contains
PROJECT ||--o{ ALGORITHM : defines

%% Media & Types
FILE_TYPE ||--o{ FILE : categorizes
FILE_TYPE }o--o{ ALGORITHM : "supported by"
USER ||--o{ FILE : uploads

%% Execution Logic
ALGORITHM ||--o{ EXECUTION : runs
FILE ||--o{ EXECUTION : "primary input"
FILE ||--o{ EXECUTION : "secondary input (optional)"
USER ||--o{ EXECUTION : triggers

%% Results
EXECUTION ||--o{ OUTPUT : generates

PROJECT {
string title
string description
datetime start_date
}
ALGORITHM {
string name
string version
string entrypoint
boolean requires_two_files
}
FILE {
string file_path
datetime upload_date
}
EXECUTION {
datetime execution_date
string status
string snapshot_alg_name
}
OUTPUT {
file annotated_media
json detection_metadata
datetime output_date
}
