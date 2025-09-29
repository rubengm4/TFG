Software Architecture

The development of this platform required careful consideration of its software architecture in order to support both the functional requirements of UAV data analysis and the non-functional requirements, such as scalability, modularity, usability, and security. The result is a layered architecture that organizes the platform into three layers: presentation, backend, and data. Each layer has its clear responsibilities and uses a combination of state-of-the-art frameworks and tools.

This architecture was designed not only to support the current project objectives, such as the analysis of solar panels and people detection, but specially to provide a solid foundation for future extensions. Thanks to its modularity, the system can integrate new AI models and algorithms, adapt to different data formats, and scale to support additional users and projects without significant redesign, as the website has been adapted for it.

Frameworks and Tools

The choice of frameworks and technologies was guided by three main principles: reliability, integration, and community support.

- Django (Backend Web Framework): Django provides a robust foundation for developing secure and maintainable web applications. Its built-in authentication system ensures safe management of users and sessions, while its ORM (Object Relational Mapping) facilitates database interaction in an abstracted, structured and maintainable way [1]. Django’s maturity and large ecosystem make it an optimal choice for a platform that requires stability and extensibility.

- PyTorch and TensorFlow (AI Frameworks): Given the AI-centric nature of the project, these frameworks were integrated to execute pre-trained models and custom algorithms. As previously covered, both are industry standards, widely used in research and production environments [2][3]. Their inclusion allows the platform to support a broad variety of models, ranging from deep learning architectures for image recognition to lighter models for tabular data analysis.

- pandas (Data Processing): Many UAV-related datasets are structured as CSV files. Pandas was chosen for its efficiency in handling this type of data, providing tools for cleaning, transformation, and aggregation [4]. Its integration ensures that the analysis workflows can process large volumes of structured data quickly.

- Grafana (Visualization): To make the results more interpretable, the platform integrates Grafana dashboards for visualization. Grafana provides dynamic and interactive panels that allow the users to explore the results in a graphical manner, improving the usability of the system in contexts such as anomaly detection or search-and-rescue operations [5].

- Frontend (Django Templates): The user interface is implemented with Django templates, ensuring seamless integration with backend functionality. The focus was placed on providing a simple, clean, responsive, and intuitive environment that minimizes the learning curve for users.

Platform Structure

The architecture of the platform follows a three-layer model, which separates user interaction, business logic, and data persistence.

- Presentation Layer
  This is the entry point for the user. The web interface provides modules for login and user creation, project selection, file upload, algorithm execution and results visualization. A responsive design ensures accessibility from different devices, making the platform usable both in field operations and in office environments. The workflow has been intentionally simplified so that a user without technical expertise in AI can still run complex analyses with only a few interactions on a very intuitive UI.

- Backend Layer
  The backend is the orchestrator of the entire system. It manages authentication and authorization through django-auth, ensuring that each user can only access their own projects and files in coordination with the data layer. It also manages the execution of AI algorithms: once a user selects a file (dataset, image or video) and an algorithm, the backend loads the corresponding model (PyTorch or TensorFlow), runs it, and stores the results for the user to see them.

  Additionally, the backend integrates analysis tools such as pandas for processing tabular data, and Grafana for generating visual dashboards. This combination makes it possible to handle diverse input types (images, videos, CSV files) and produce outputs ranging from structured tables to interactive visualizations.

- Data Layer
  The data layer defines the persistence model through Django ORM. It includes entities for users, projects, files, algorithms, executions, and outputs. Each entity has been carefully modeled to reflect real-world interactions:

  Projects organize workspaces.

  Files represent the data to be analyzed, classified by type (image, video, CSV).

  Algorithms register AI models along with metadata such as version and supported file types.

  Executions log each algorithm run, linking inputs with outputs and maintaining traceability.

  Outputs store and expose the results for later visualization or download.

  This relational model not only guarantees consistency but also allows the reproduction of experiments, which is critical in academic and industrial environments.

- Platform Diagram

The architecture is visually summarized in Figure 1, which represents the three layers of the platform.

The presentation layer (red nodes) contains the user interface components, including login, project management, file upload, algorithm selection, analysis, and reporting.

The backend layer (blue nodes) handles authentication, algorithm execution (via PyTorch/TensorFlow), and analysis tasks (with pandas and Grafana).

The data layer (green nodes) represents the database schema, where models define how projects, files, algorithms, executions, and outputs are stored and related.

Arrows illustrate the flow of data: user actions in the interface are routed through the backend, which processes them, interacts with the database, and eventually produces outputs that are fed back into the analysis and reporting modules.

Figure 1: Software architecture of the UAV IoT platform.

- Deployment and Environment

To ensure reproducibility and portability, the platform was designed with deployment flexibility in mind. In its current state, it can be deployed locally for development and testing, but the architecture also supports cloud-based deployment for production use.

Application Hosting: The Django application can be deployed on traditional web servers (e.g., Gunicorn + Nginx) or containerized environments such as Docker, which simplifies distribution and ensures consistent environments across machines [6].

Database: For persistence, the platform relies on relational databases supported by Django ORM (e.g., PostgreSQL or MySQL in development).

AI Model Execution: The integration of PyTorch and TensorFlow makes it possible to take advantage of GPUs for acceleration. In a production environment, this could be hosted on cloud services that provide GPU-enabled instances (e.g., AWS, Google Cloud, or Azure) [8]. For smaller-scale deployments, CPU execution is still possible, though less efficient.

Visualization Services: Grafana can be deployed as a standalone service connected to the backend database. This separation of concerns allows scaling the visualization independently of the main application, ensuring responsiveness even under heavy data loads.

Scalability Considerations: By adopting containerization (Docker) and orchestration platforms (e.g., Kubernetes), the system could scale horizontally, supporting multiple concurrent users and heavier workloads, which is particularly relevant in scenarios involving large UAV missions [9].

This deployment flexibility ensures that the platform is not only usable in a laboratory context but also ready for real-world applications, ranging from academic experiments to industrial-scale UAV operations.

Security Considerations

Security is a fundamental aspect of any platform that manages sensitive data, particularly in contexts such as UAV operations, where the information may involve infrastructure, logistics, or emergency scenarios. Several mechanisms have been implemented or considered in the design of the system:

Authentication and Authorization: Django’s built-in authentication system ensures secure user login and session handling [1]. Role-based access control can be applied to restrict access to certain features, ensuring that only authorized users can execute, create and manage algorithms or enter in specific projects.

Data Isolation: Each project is associated with specific users, and permissions are enforced at the database level through relational models. This prevents unauthorized access to files or results belonging to other users, ensuring data confidentiality in multi-user environments. Therefore, only users registered in that project can enter the project.

File Handling: Uploaded files are validated before being stored to prevent harmful content or incompatible formats. By separating metadata (stored in the database) from the actual files (stored in the file system or cloud storage), the risk of corruption or accidental overwriting is minimized.

Secure Communication: In a production deployment, all communication between client and server should be encrypted using HTTPS, ensuring confidentiality and integrity during file uploads or result downloads [10].

Auditability and Traceability: The platform records each algorithm execution, including metadata such as user, timestamp, and input files. This not only provides reproducibility but also serves as an audit trail, which is essential for accountability in academic research or industrial operations.

By integrating these mechanisms, the platform balances usability with robust safeguards, making it suitable for real-world scenarios where both accuracy and trustworthiness are required.

Limitations and Future Improvements

Despite its current functionality, the platform has some limitations that open the door for future work and improvements:

Real-Time Processing: At present, the platform focuses on batch analysis of files uploaded by the user. Real-time data streams from UAV cameras or similar are not yet supported. Future versions could integrate edge computing or message brokers (e.g., MQTT, Kafka) to enable real-time analysis [11].

Dependence on Pre-Trained Models: The algorithms currently integrated are based on pre-trained models. While these are effective, they may not always adapt perfectly to new environments or specific UAV missions. Extending the platform with training pipelines would enhance adaptability, and if the model could learn with each iteration, this could make it even more powerful.

Scalability at Large Scale: Although the platform is container-ready, real-world deployments with dozens of drones, thousands of users and terabytes of data per day, including their uploaded files and their analysis, would require distributed storage and more advanced orchestration, such as Kubernetes clusters with GPU scheduling in order to manage that much information [9].

User Experience and Accessibility: While the current interface is functional, future work could improve accessibility, provide multilingual support, integrate mobile-first interfaces for field operations, or make the UI more user-friendly, with more sophisticaed styles.

Integration with IoT Ecosystems: The architecture could be extended to interact directly with IoT platforms and UAV control systems, closing the loop between data collection, analysis, and autonomous decision-making [12].

By addressing these limitations, the platform can evolve into a more comprehensive and production-ready solution, with greater applicability in industrial and emergency contexts.

- Design Considerations and Justification

The layered design was chosen to maximize modularity: each layer can evolve independently. For example, the frontend could be replaced by a JavaScript framework in the future, such as React, without modifying the backend logic, or new AI algorithms can be added to the backend without altering the database schema, only adding them on the project, as this would create the entry on the database.

The reliance on established frameworks (Django, PyTorch, TensorFlow, pandas, Grafana) guarantees reliability and long-term maintainability. These tools are not only well-supported by large communities but also widely adopted in both academic and industrial contexts, ensuring continuity and the abscense of future vulnerabilities, as this would be mantained by the application developers.

Another key consideration was usability. Many IoT and AI platforms require technical expertise, which can be a barrier for adoption. By prioritizing simplicity in the workflow and providing graphical interfaces for data visualization, the platform lowers this barrier, making AI-powered analysis more accessible to every user, independently of its expertise level.

Finally, the architecture was designed with scalability, security, and future extensibility in mind. New projects, files, algorithms, and even new data types can be integrated without significant changes to the core. Likewise, strong user management and data isolation ensure that the platform remains trustworthy and safe in multi-user scenarios. This ensures that the system can grow together with emerging needs, from supporting more UAV missions to incorporating real-time data streams in future iterations.

References (placeholders for you to replace with proper citations)

[1] Django Software Foundation. Django Documentation. https://www.djangoproject.com/

[2] Paszke et al. PyTorch: An Imperative Style, High-Performance Deep Learning Library.
[3] Abadi et al. TensorFlow: Large-Scale Machine Learning on Heterogeneous Systems.
[4] Wes McKinney. Python for Data Analysis: Data Wrangling with Pandas, NumPy, and IPython.
[5] Grafana Labs. Grafana Documentation. https://grafana.com/docs/

[6] Gunicorn Documentation. Gunicorn WSGI Server for Python.
[7] PostgreSQL Global Development Group. PostgreSQL Documentation. https://www.postgresql.org/docs/

[8] Amazon Web Services. Amazon EC2 P3 Instances for Machine Learning.
[9] Kubernetes Documentation. Kubernetes Concepts. https://kubernetes.io/docs/

[10] Mozilla. Security/Server Side TLS. https://wiki.mozilla.org/Security/Server_Side_TLS

[11] Kreps et al. Kafka: a Distributed Messaging System for Log Processing.
[12] MQTT.org. MQTT Protocol Specification. https://mqtt.org/
