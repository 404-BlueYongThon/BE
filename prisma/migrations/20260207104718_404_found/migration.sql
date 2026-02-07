/*
  Warnings:

  - Added the required column `latitude` to the `hospital` table without a default value. This is not possible if the table is not empty.
  - Added the required column `longitude` to the `hospital` table without a default value. This is not possible if the table is not empty.
  - Made the column `name` on table `hospital` required. This step will fail if there are existing NULL values in that column.
  - Made the column `max_grade` on table `hospital` required. This step will fail if there are existing NULL values in that column.
  - Made the column `min_grade` on table `hospital` required. This step will fail if there are existing NULL values in that column.
  - Made the column `created_at` on table `hospital` required. This step will fail if there are existing NULL values in that column.
  - Made the column `updated_at` on table `hospital` required. This step will fail if there are existing NULL values in that column.
  - Made the column `number` on table `hospital` required. This step will fail if there are existing NULL values in that column.
  - Made the column `created_at` on table `hospital-requests` required. This step will fail if there are existing NULL values in that column.
  - Made the column `age` on table `patient` required. This step will fail if there are existing NULL values in that column.
  - Made the column `category` on table `patient` required. This step will fail if there are existing NULL values in that column.
  - Made the column `symptom` on table `patient` required. This step will fail if there are existing NULL values in that column.
  - Made the column `remarks` on table `patient` required. This step will fail if there are existing NULL values in that column.
  - Made the column `grade` on table `patient` required. This step will fail if there are existing NULL values in that column.
  - Made the column `created_at` on table `patient` required. This step will fail if there are existing NULL values in that column.

*/
-- AlterTable
ALTER TABLE `hospital` ADD COLUMN `latitude` DECIMAL(10, 8) NOT NULL,
    ADD COLUMN `longitude` DECIMAL(11, 8) NOT NULL,
    MODIFY `name` VARCHAR(30) NOT NULL,
    MODIFY `max_grade` INTEGER NOT NULL,
    MODIFY `min_grade` INTEGER NOT NULL,
    MODIFY `created_at` DATETIME(6) NOT NULL,
    MODIFY `updated_at` DATETIME(6) NOT NULL,
    MODIFY `number` VARCHAR(30) NOT NULL;

-- AlterTable
ALTER TABLE `hospital-requests` MODIFY `created_at` DATETIME(6) NOT NULL;

-- AlterTable
ALTER TABLE `patient` MODIFY `age` VARCHAR(20) NOT NULL,
    MODIFY `category` VARCHAR(20) NOT NULL,
    MODIFY `symptom` VARCHAR(20) NOT NULL,
    MODIFY `remarks` VARCHAR(50) NOT NULL,
    MODIFY `grade` INTEGER NOT NULL,
    MODIFY `created_at` DATETIME(6) NOT NULL;
