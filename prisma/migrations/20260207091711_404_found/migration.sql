-- CreateTable
CREATE TABLE `patient` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `age` VARCHAR(20) NULL,
    `category` VARCHAR(20) NULL,
    `symptom` VARCHAR(20) NULL,
    `remarks` VARCHAR(50) NULL,
    `grade` INTEGER NULL,
    `created_at` DATETIME(6) NULL,

    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `hospital` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(30) NULL,
    `max_grade` INTEGER NULL,
    `min_grade` INTEGER NULL,
    `created_at` DATETIME(6) NULL,
    `updated_at` DATETIME(6) NULL,

    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `hospital-requests` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `patient_id` INTEGER NOT NULL,
    `hospital_id` INTEGER NOT NULL,
    `accepted` BOOLEAN NULL,
    `created_at` DATETIME(6) NULL,

    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- AddForeignKey
ALTER TABLE `hospital-requests` ADD CONSTRAINT `hospital-requests_patient_id_fkey` FOREIGN KEY (`patient_id`) REFERENCES `patient`(`id`) ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `hospital-requests` ADD CONSTRAINT `hospital-requests_hospital_id_fkey` FOREIGN KEY (`hospital_id`) REFERENCES `hospital`(`id`) ON DELETE CASCADE ON UPDATE CASCADE;
