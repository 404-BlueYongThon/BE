/*
  Warnings:

  - Added the required column `sex` to the `patient` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE `patient` ADD COLUMN `sex` VARCHAR(10) NOT NULL;
