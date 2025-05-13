-- Table: Project
CREATE TABLE `Project` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255),
    `description` TEXT,
    `start_date` DATE
);

-- Table: User
CREATE TABLE `User` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(100) NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `email` VARCHAR(255) NOT NULL UNIQUE,
    `joined_date` DATE
);

-- Table: File
CREATE TABLE `File` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT,
    `name` VARCHAR(255),
    `type` ENUM('csv', 'image', 'video'),
    `upload_date` DATE,
    FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE SET NULL,
    INDEX (`user_id`)
);

-- Table: Algorithm
CREATE TABLE `Algorithm` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255),
    `version` VARCHAR(50),
    `description` TEXT
);

-- Table: Execution
CREATE TABLE `Execution` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT,
    `algorithm_id` INT,
    `file_id` INT,
    `execution_date` DATE,
    `status` ENUM('PENDING', 'FINISHED', 'FAILED'),
    FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`algorithm_id`) REFERENCES `Algorithm`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`file_id`) REFERENCES `File`(`id`) ON DELETE SET NULL,
    INDEX (`user_id`),
    INDEX (`algorithm_id`),
    INDEX (`file_id`)
);

-- Table: Report
CREATE TABLE `Report` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `execution_id` INT,
    `path` TEXT,
    `report_date` DATE,
    FOREIGN KEY (`execution_id`) REFERENCES `Execution`(`id`) ON DELETE CASCADE,
    INDEX (`execution_id`)
);

-- Table: UserProject (many-to-many relationship)
CREATE TABLE `UserProject` (
    `project_id` INT,
    `user_id` INT,
    `joined_at` DATE,
    `role` VARCHAR(100),
    PRIMARY KEY (`project_id`, `user_id`),
    FOREIGN KEY (`project_id`) REFERENCES `Project`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE CASCADE,
    INDEX (`user_id`),
    INDEX (`project_id`)
);
