# Project Definition Document

**Project:** Green Software Metrics Framework (GSMF)
**Course:** BIL 481 Software Engineering, Fall 2026
**Group:** Intellectual Property
**Document date:** 01-11-2026

**Contributors to this document:** Reşat Efe Koca (231301010), Bülent Çakır (231301064), Murat Yılmaz (241101063), Furkan Yaman (221301015)

\---

## Table of Contents

1. [Project Name](#1-project-name)
2. [Project Summary](#2-project-summary)
3. [Objectives](#3-objectives)
4. [Scope](#4-scope)
5. [Target Audience](#5-target-audience)
6. [Key Features](#6-key-features)
7. [Deliverables](#7-deliverables)
8. [Budget and Resources](#8-budget-and-resources)
9. [Risks and Mitigation Strategies](#9-risks-and-mitigation-strategies)
10. [Project Success Criteria](#10-project-success-criteria)
11. [Document-Specific Task Matrix](#11-document-specific-task-matrix)

\---

## 1\. Project Name

**Green Software Metrics Framework (GSMF)** — an energy and efficiency benchmarking harness for low-code platforms.

## 2\. Project Summary

Low-code platforms let teams build applications quickly, but the runtime energy cost of their abstraction layers is rarely measured. Developers and organizations therefore have no reliable way to tell how energy-efficient a low-code application is compared to a hand-coded equivalent.

GSMF is a command-line benchmarking framework that measures and compares the energy consumption and efficiency of the same reference application built on self-hosted low-code platforms (Budibase and Appsmith, running in Docker) and on a hand-coded FastAPI baseline. It reads CPU energy directly from Linux RAPL counters, drives a standardized workload from a separate load-generator machine, applies controlled experimental conditions, and reports energy per user task, Energy-Delay Product (EDP) and the operational Software Carbon Intensity (SCI) score defined by the Green Software Foundation.

## 3\. Objectives

By the end of the project we aim to:

1. Implement the same reference CRUD application (create item, paginated list, batch update) on Budibase, Appsmith and FastAPI.
2. Build a Python CLI that runs one platform stack at a time, measures idle and workload energy via RAPL, and computes net energy.
3. Run at least 10 repetitions per platform under controlled conditions (fixed CPU governor, Turbo Boost off, cooldown between runs).
4. Report mean energy, execution time, EDP and operational SCI per completed user task, with 95% confidence intervals.
5. Provide a simple results dashboard and CSV/report export so results can be compared and reproduced.

## 4\. Scope



## 5\. Target Audience



## 6\. Key Features



## 7\. Deliverables



## 8\. Budget and Resources



## 9\. Risks and Mitigation Strategies



## 10\. Project Success Criteria



## 11\. Document-Specific Task Matrix

|Task|Responsible|
|-|-|
|Project name, summary and objectives|Reşat Efe Koca|
|Scope and target audience|Murat Yılmaz|
|Key features and deliverables|Bülent Çakır|
|Budget, resources, risks and mitigation|Furkan Yaman|
|Success criteria|Bülent Çakır|
|Review, formatting and final PDF|Reşat Efe Koca|



