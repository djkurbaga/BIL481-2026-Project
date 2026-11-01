# Requirements Document

**Project:** Green Software Metrics Framework (GSMF)
**Course:** BIL 481 Software Engineering, Fall 2026
**Group:** Intellectual Property
**Document date:** 01-11-2026

**Contributors to this document:**

|Name|GitHub|School Number|
|-|-|-|
|Reşat Efe Koca|@djkurbaga|231301010|
|Bülent Çakır|@BulentCakirr|231301064|
|Murat Yılmaz|@yilmazmurat06|241101063|
|Furkan Yaman|@furkany22|221301015|

\---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Definitions](#2-definitions)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [Document-Specific Task Matrix](#5-document-specific-task-matrix)

\---

## 1\. Introduction

This document lists the functional and non-functional requirements of GSMF, a CLI-based framework that measures and compares the energy consumption and efficiency of the same reference application running on Budibase, Appsmith (self-hosted in Docker) and a hand-coded FastAPI baseline. Each requirement is numbered and written so that it can be verified by a test or a demonstration.

## 2\. Definitions

* **Target:** one platform stack under test (Budibase, Appsmith or FastAPI baseline).
* **Testbed:** the Linux machine that runs the target and reads RAPL energy counters.
* **Load generator:** a separate machine that runs the k6 workload against the testbed.
* **User task (R):** one completed sequence of create item + paginated list + batch update.
* **Net energy:** gross RAPL energy during the workload minus idle power × workload duration.
* **EDP:** Energy-Delay Product = net energy (J) × duration (s).
* **Operational SCI:** (E × I) / R, where E is net energy in kWh, I is grid carbon intensity (gCO2eq/kWh), reported per 1,000 user tasks.

## 3\. Functional Requirements

## 4\. Non-Functional Requirements

## 5\. Document-Specific Task Matrix

|Task|Responsible|
|-|-|
|Introduction and definitions|Reşat Efe Koca|
|Functional requirements FR-1 to FR-7|Murat Yılmaz|
|Functional requirements FR-8 to FR-14|Reşat Efe Koca|
|Non-functional requirements|Furkan Yaman|
|Verification column and consistency review|Bülent Çakır|
|Formatting and final PDF|Bülent Çakır|



