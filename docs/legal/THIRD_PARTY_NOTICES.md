# ResearchLens — Third-Party Software Notices & Open Source Licenses

This document contains licensing, copyright, and intellectual property notices for open-source and third-party software components bundled with, executed by, or interfaced with the **ResearchLens** platform and desktop application.

---

## 1. Project License Overview

ResearchLens is licensed under the **GNU Affero General Public License version 3.0** (AGPL-3.0). See [LICENSE](../../LICENSE) for the full license text.

Individual copyright is retained by the project authors:
- Copyright (C) 2026 Gorav Gumber
- Copyright (C) 2026 Himanshu Kumawat
- Copyright (C) 2026 Harendra Godara
- Copyright (C) 2026 Abhay Kumar Singh

---

## 2. Bundled Native Runtimes

### Python Runtime
- **Version:** Python 3.12 (CPython)
- **License:** Python Software Foundation License Version 2 (PSF-2.0)
- **Copyright:** (c) 2001–2026 Python Software Foundation. All Rights Reserved.
- **Upstream:** https://www.python.org/
- **Bundled:** Yes (packaged in desktop installer `app-runtime/python/`)

### Electron Framework
- **Version:** 39.8.10
- **License:** MIT License
- **Copyright:** (c) Electron contributors / OpenJS Foundation
- **Upstream:** https://www.electronjs.org/
- **Bundled:** Yes (native desktop application container)

---

## 3. Document Extraction & OCR Components

### PyMuPDF (and MuPDF)
- **Version:** PyMuPDF 2.1 (wrapping MuPDF 1.28.6)
- **License:** GNU Affero General Public License v3.0 (AGPL-3.0) / Artifex Commercial License
- **Copyright:** (c) 2013–2026 Artifex Software, Inc.
- **Upstream:** https://github.com/pymupdf/PyMuPDF
- **Bundled:** Yes (packaged in desktop installer Python environment for PDF ingestion)
- **License Terms:** Distributed under the terms of the GNU Affero General Public License version 3.0. Complete corresponding source code is made available in accordance with AGPL-3.0 Section 6.

### Tesseract OCR Language Data
- **Artifact:** `eng.traineddata` (English OCR model)
- **License:** Apache License, Version 2.0
- **Copyright:** (c) 2006–2026 Google LLC and Tesseract OCR contributors
- **Upstream:** https://github.com/tesseract-ocr/tessdata
- **Bundled:** Yes (`rag/resources/tessdata/eng.traineddata`)

---

## 4. Python Backend & Research Engine Dependencies

The following Python packages are executed by or bundled with the ResearchLens backend and RAG engine:

| Package | Version | License | Upstream / Copyright | Bundled in Desktop |
|---|---|---|---|---|
| **FastAPI** | 0.162.5 | MIT | (c) 2018–2026 Sebastián Ramírez | Yes |
| **Uvicorn** | 0.54.0 | BSD-3-Clause | (c) 2017–2026 Encode OSS Ltd. | Yes |
| **Pydantic** | 2.14.3 | MIT | (c) 2017–2026 Samuel Colvin / Pydantic Services Inc. | Yes |
| **Pydantic-Settings** | 2.16.2 | MIT | (c) 2023–2026 Samuel Colvin / Pydantic Services Inc. | Yes |
| **SQLAlchemy** | 2.1.8 | MIT | (c) 2005–2026 Michael Bayer / SQLAlchemy authors | Yes |
| **aiosqlite** | 0.22.1 | MIT | (c) 2018–2026 John Reese | Yes |
| **asyncpg** | 0.32.0 | Apache-2.0 | (c) 2016–2026 MagicStack Inc. | Yes |
| **Alembic** | 1.20.1 | MIT | (c) 2009–2026 Michael Bayer | Yes |
| **PyJWT** | 2.15.1 | MIT | (c) 2015–2026 José Padilla | Yes |
| **bcrypt** | 5.0.0 | Apache-2.0 | (c) 2013–2026 The Python Cryptographic Authority | Yes |
| **python-docx** | 1.2.0 | MIT | (c) 2013–2026 Steve Canny | Yes |
| **openpyxl** | 3.1.5 | MIT | (c) 2010–2026 Eric Gazoni, Charlie Clark | Yes |
| **python-pptx** | 1.0.2 | MIT | (c) 2013–2026 Steve Canny | Yes |
| **python-multipart** | 0.0.33 | Apache-2.0 | (c) 2014–2026 Andrew Dunham | Yes |
| **python-dotenv** | 1.2.4 | BSD-3-Clause | (c) 2014–2026 Saurabh Kumar | Yes |
| **pypdf** | 7.0.1 | BSD-3-Clause | (c) 2006–2026 Mathieu Fenniak / pypdf contributors | Yes |
| **email-validator** | 2.3.0 | The Unlicense | Dedicated to public domain by Joshua Tauberer | Yes |
| **greenlet** | 3.5.6 | MIT & PSF-2.0 | (c) 2004–2026 Alexey Borzenkov / contributors | Yes |
| **httpx** | 0.28.1 | BSD-3-Clause | (c) 2019–2026 Encode OSS Ltd. | Yes |
| **NumPy** | 2.5.4 | BSD-3-Clause | (c) 2005–2026 NumPy Developers | Yes |
| **scikit-learn** | 1.9.1 | BSD-3-Clause | (c) 2007–2026 scikit-learn developers | Yes |
| **joblib** | 1.6.0 | BSD-3-Clause | (c) 2008–2026 Joblib developers | Yes |
| **Rich** | 15.0.0 | MIT | (c) 2020–2026 Will McGugan | Yes |

*Note: Optional server-mode packages such as ChromaDB, FastEmbed, and Google-GenAI are not bundled into the desktop release installer.*

---

## 5. Web & Frontend Dependencies

The following JavaScript/Node.js packages are compiled into or bundled with the ResearchLens desktop frontend:

| Package | Version | License | Upstream / Copyright | Bundled in Desktop |
|---|---|---|---|---|
| **Next.js** | 15.5.28 | MIT | (c) 2026 Vercel, Inc. | Yes (Standalone SSR) |
| **React & React-DOM** | 18.3.1 | MIT | (c) 2026 Meta Platforms, Inc. | Yes |
| **Radix UI Primitives** | ~1.1.0–2.1.2 | MIT | (c) 2022–2026 WorkOS | Yes |
| **Lucide Icons** | 0.453.0 | ISC | (c) 2022–2026 Lucide Contributors | Yes |
| **KaTeX** | 0.19.0 | MIT | (c) 2013–2026 Khan Academy and other contributors | Yes |
| **pdfjs-dist** | 4.10.38 | Apache-2.0 | (c) 2011–2026 Mozilla Foundation | Yes |
| **Zustand** | 5.0.15 | MIT | (c) 2019–2026 Paul Henschel / Zustand contributors | Yes |
| **Tailwind CSS** | 3.4.19 | MIT | (c) 2017–2026 Tailwind Labs, Inc. | Compiled into CSS |
| **clsx** | 2.1.1 | MIT | (c) 2026 Luke Edwards | Yes |
| **tailwind-merge** | 2.6.1 | MIT | (c) 2026 Dany Castillo | Yes |
| **class-variance-authority** | 0.7.1 | Apache-2.0 | (c) 2022–2026 Joe Bell | Yes |

---

## 6. Typography & Font Licenses

### Inter Variable Font
- **License:** SIL Open Font License, Version 1.1 (OFL-1.1)
- **Copyright:** (c) 2016–2026 The Inter Project Authors
- **Upstream:** https://github.com/rsms/inter
- **Bundled:** Yes (`desktop/onboarding/fonts/`, `desktop/startup/fonts/`)

### JetBrains Mono Variable Font
- **License:** SIL Open Font License, Version 1.1 (OFL-1.1)
- **Copyright:** (c) 2020–2026 JetBrains s.r.o.
- **Upstream:** https://www.jetbrains.com/lp/mono/
- **Bundled:** Yes (imported via `@fontsource-variable/jetbrains-mono`)

---

## 7. Public Domain Software

### SQLite
- **License:** Public Domain
- **Author:** D. Richard Hipp and SQLite contributors
- **URL:** https://www.sqlite.org/
- **Usage:** Embedded transactional library database and FTS5 full-text lexical search index.
- All code and documentation in SQLite have been dedicated to the public domain by the authors.

---

## 8. Common Open Source License Texts

### MIT License
```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### ISC License
```text
Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

### Apache License, Version 2.0 (Summary Notice)
```text
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### SIL Open Font License 1.1 (Summary Notice)
```text
This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```
