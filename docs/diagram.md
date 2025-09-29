flowchart LR
%% === Presentation Layer ===
subgraph Presentation
UI_Login["Login (Django Auth)"]
UI_Project["Project Selection"]
UI_File["File Upload"]
UI_Alg["Algorithm Selection"]
UI_Analysis["Analysis Tab"]
UI_Report["Report View"]
end

%% === Backend Layer ===
subgraph Backend
DjangoAuth(("Django Auth - User management"))
AlgoExec["Algorithm Execution - Python / PyTorch / TensorFlow"]
Analysis["Analysis - pandas + Grafana"]
end

%% === Data Layer ===
subgraph Data
ProjectModel["Project - title, description, start_date"]
UserProjectModel["UserProject - user (FK User), project (FK Project), joined_at"]
FileTypeModel["FileType - code, name"]
FileModel["File - user (FK User), file, type (FK FileType), upload_date"]
AlgorithmModel["Algorithm - name, project (FK Project), version, description, archive, entrypoint, supported_types (M2M FileType), requires_two_files"]
ExecutionModel["Execution - user (FK User), algorithm (FK Algorithm), file (FK File), secondary_file (FK File), execution_date, status, snapshot_file_name, snapshot_alg_name"]
OutputModel["Output - execution (FK Execution), file, output_date"]
end

%% === Flows ===
UI_Login --> DjangoAuth
UI_Project --> DjangoAuth
UI_File --> AlgoExec
UI_Alg --> AlgoExec
UI_Analysis --> Analysis
UI_Report --> Analysis

DjangoAuth --> ProjectModel
AlgoExec --> ExecutionModel
Analysis --> OutputModel

ProjectModel --- AlgorithmModel
ProjectModel --- UserProjectModel
FileModel --- FileTypeModel
AlgorithmModel --- FileTypeModel
ExecutionModel --- AlgorithmModel
ExecutionModel --- FileModel
OutputModel --- ExecutionModel

%% === Colors ===
style UI_Login fill:#FEE2E2,stroke:#EF4444,stroke-width:1px
style UI_Project fill:#FEE2E2,stroke:#EF4444,stroke-width:1px
style UI_File fill:#FEE2E2,stroke:#EF4444,stroke-width:1px
style UI_Alg fill:#FEE2E2,stroke:#EF4444,stroke-width:1px
style UI_Analysis fill:#FEE2E2,stroke:#EF4444,stroke-width:1px
style UI_Report fill:#FEE2E2,stroke:#EF4444,stroke-width:1px

style DjangoAuth fill:#DBEAFE,stroke:#3B82F6,stroke-width:1px
style AlgoExec fill:#DBEAFE,stroke:#3B82F6,stroke-width:1px
style Analysis fill:#DBEAFE,stroke:#3B82F6,stroke-width:1px

style ProjectModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
style UserProjectModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
style FileTypeModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
style FileModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
style AlgorithmModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
style ExecutionModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
style OutputModel fill:#D1FAE5,stroke:#10B981,stroke-width:1px
