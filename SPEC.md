# STUDS Functional Specification

Exhaustive checklist of every user-facing feature and observable behavior.

---

## Auth

### Landing Page (`/`)
- [ ] Displays STUDS logo with "(CONFIDENTIAL)" label
- [ ] Shows two portal buttons: STUDIO (lime) and HQ (lavender)
- [ ] STUDIO button navigates to `/studio/login`
- [ ] HQ button navigates to `/hq/login`

### Studio Login (`/studio/login`)
- [ ] Displays username and password fields
- [ ] Username field is autofocused
- [ ] Submitting valid store credentials logs in and redirects to `/studio/`
- [ ] Submitting the admin shortcut credentials (hq/hq) logs in as admin, bypasses lockout
- [ ] Submitting invalid credentials shows "Incorrect username or password." flash message
- [ ] Submitting valid credentials for a store whose timezone is Friday-Sunday shows lockout message: "Sorry, stud! The new SKU list will be available Monday."
- [ ] Lockout check is timezone-aware per store (Friday 00:00 through Sunday 23:59 in the store's local timezone)
- [ ] Lockout can be disabled via `feature_studio_lockout` setting in settings.json
- [ ] Back link navigates to landing page

### HQ Login (`/hq/login`)
- [ ] Displays username and password fields
- [ ] Username field is autofocused
- [ ] Submitting the admin shortcut credentials (hq/hq) logs in and redirects to `/hq/`
- [ ] Submitting valid hq_users credentials logs in with display name shown in header
- [ ] Submitting invalid credentials shows "Incorrect username or password." flash message
- [ ] Back link navigates to landing page
- [ ] "(CONFIDENTIAL)" label displayed

### Session & Logout
- [ ] Studio logout (`/studio/logout`) clears studio session and redirects to landing page
- [ ] HQ logout (`/hq/logout`) clears HQ session and redirects to landing page
- [ ] Accessing any `/studio/` route without session redirects to studio login
- [ ] Accessing any `/hq/` route without session redirects to HQ login

### Portal Switching
- [ ] HQ header contains STUDIO link that navigates to `/hq/goto-studio`, which sets studio session and redirects to `/studio/`
- [ ] Admin users in Studio portal see an HQ link that navigates to `/studio/goto-hq`, which sets HQ session and redirects to `/hq/`

---

## HQ Portal (`/hq/`)

### SPA Shell (applies to all HQ sections)
- [ ] Header displays STUDS logo with "(CONFIDENTIAL)" label
- [ ] Left nav box (lime): HQ (current/bold) | STUDIO | LOGOUT
- [ ] Right nav box (lavender): FILES | REFRESH | SETTINGS
- [ ] User display name shown below header (if logged in as named user)
- [ ] "UPDATED:" timestamp shown below header, updates on refresh

> **⚠️ Updated in sandbox:** The DASHBOARD tab has been retired. See Sandbox Changes — Dashboard Retirement.

- [ ] Section nav bar: ANALYTICS | DATABASE | STUDIOS
- [ ] Clicking a section link loads its content via AJAX into the main area without full page reload
- [ ] Active section link is visually highlighted
- [ ] Browser back/forward buttons navigate between sections via history.pushState
- [ ] Direct URL access with `?section=` parameter loads the correct section on page load
- [ ] Default section on initial page load (no `?section=` param): Analytics
- [ ] Page scrolls to top when switching sections

### Refresh
- [ ] REFRESH button in header sends POST to `/hq/refresh`
- [ ] On success, updates the "UPDATED:" timestamp in the header
- [ ] On failure, shows an alert with the error

### Export CSV (`/hq/export`)
- [ ] Downloads a CSV file named `STUDS_Dashboard_Export_YYYYMMDD_HHMMSS.csv`
- [ ] CSV columns: Store ID, Store Name, Status, SKU, Product ID, Required Push, Location, Item Cost Price, Actual Push, Discrepancy
- [ ] Includes all SKU detail rows for stores that have variance data
- [ ] Stores without data get a single row with empty SKU fields

### Dashboard (Retired)

> **⚠️ Retired in sandbox.** The old Dashboard tab and its fragment (`templates/fragments/dashboard.html`) have been deleted. `GET /hq/section/dashboard` now redirects to `/hq/section/analytics`. Bookmarked or cached links to the dashboard gracefully land on Analytics. See Sandbox Changes — Dashboard Retirement for full detail.
>
> The following features existed in the old Dashboard and are **no longer present**:

- ~~Summary bar (Total Studios / Updated / Discrepancy / Incomplete / SKU filename / SKU count / audit date range)~~
- ~~Bypass banner (no SKU list loaded warning)~~
- ~~Reconciliation warnings~~
- ~~Filter (All/Updated/Discrepancy/Incomplete) and Sort (Store ID/Status/Discrepancy Count) controls~~
- ~~EXPORT CSV and ARCHIVE action links~~
- ~~Per-store reconciliation table with expand/collapse detail rows~~
- ~~SKU-level detail rows with Required Push / Actual Push / Discrepancy~~
- ~~GENERATE EMAIL button and Email Draft modal~~
- ~~Dashboard reload on REFRESH~~

---

## HQ Analytics (`/hq/?section=analytics`)

> **⚠️ Replaced in sandbox.** The old analytics section (fake data, 6 scroll-anchored pseudo-tabs) was deleted and replaced with a real 3-tab analytics UI backed by the `stock_checks` / `stock_check_skus` tables. This is now the default landing section after HQ login. See Sandbox Changes — HQ Analytics Replacement for full detail.

### Sub-Navigation
- [ ] Sticky sub-nav bar with three tab links: OVERVIEW | PARTICIPATION | LEADERBOARD
- [ ] Sub-nav hoisted into the sticky header on section load (via `loadSection()` in `hq_shell.html`)
- [ ] Active tab is underlined; inactive tabs are not
- [ ] Clicking a tab link switches the content area without reloading the section
- [ ] Right side of sub-nav: RANGE label + dropdown selector (Last 4 weeks / Last 12 weeks / All time; default: Last 4 weeks)
- [ ] Range selection is shared across all three tabs
- [ ] Changing the range clears the client-side cache and refetches the current tab

### Data Source
- [ ] All analytics data is read from `stock_checks` and `stock_check_skus` tables in `store_profiles.db`
- [ ] No fake or randomly-generated data exists anywhere in the codebase
- [ ] "Abandoned" status is computed at query time: `status = 'abandoned'` OR (`status = 'in_progress'` AND `started_at < now − 3 days`); the DB column itself is not rewritten
- [ ] All four analytics API routes require `@hq_login_required`

### Overview Tab (`GET /hq/analytics/overview?range=`)
- [ ] Headline: "X of Y studios completed their stock check this week (ZZ%)" — color-coded green (≥80%), amber (60–79%), red (<60%)
- [ ] Week identifier (MM/DD/YY) shown below headline
- [ ] Four stat boxes: Avg Completion Time | Variances Found | Variances Reconciled | Variances Still Off
- [ ] Full-width line chart: "Network-Wide Variance Trend" — two datasets (Variances Found avg per run, Variances Still Off avg per run) across weeks in range
- [ ] If no data: empty-state message instead of chart and stats
- [ ] Chart.js 4.x loaded from CDN (`cdn.jsdelivr.net/npm/chart.js@4.4.0`)

### Participation Tab (`GET /hq/analytics/participation?range=`)
- [ ] Sortable table: Studio | Region | This Week | Last 4 Weeks | Runs in Range
- [ ] This Week column: colored badge — ✓ Completed (green) / ⏳ In Progress (amber) / ⚠ Abandoned (amber) / ✕ Didn't Start (gray)
- [ ] Last 4 Weeks column: four 12×12 colored squares (green=completed, amber=abandoned/in-progress, gray=didn't start)
- [ ] Default sort: studios that didn't start this week at top; completed at bottom; secondary sort by store ID ascending
- [ ] All columns except Last 4 Weeks are sortable by clicking headers
- [ ] If no data: empty-state message

### Leaderboard Tab (`GET /hq/analytics/leaderboard?range=`)
- [ ] Sortable table: Rank | Studio | Region | Score | Completion Rate | Follow-Through | Adjustment Success
- [ ] Score: composite 0–100, weighted sum of three rates (weights tunable at top of `analytics_begin_count.py`: Completion 40%, Adjustment 35%, Follow-Through 25%)
- [ ] Completion Rate: `completed weeks / total weeks in range`
- [ ] Follow-Through: `completed runs / started runs`
- [ ] Adjustment Success: `variances_reconciled / total_variances` across completed runs
- [ ] Default sort: Score descending (rank ascending)
- [ ] All columns sortable; sort is maintained across drill-down open/close
- [ ] Clicking a row expands an in-place drill-down row below it; clicking again collapses it
- [ ] Re-sorting the table collapses any open drill-down first

### Leaderboard Drill-Down (`GET /hq/analytics/studio/<store_id>?range=`)
- [ ] Fetched on expand; shows "Loading studio details…" placeholder while fetching
- [ ] Step Funnel: bar chart (Chart.js) with steps 1–7 on X-axis, run-count on Y-axis; callout text names the step with the biggest drop-off
- [ ] Variance Trend: line chart with two datasets (Variances Found / Variances Still Off per completed run over time)
- [ ] Recent Runs table: Started | Counter | Status | Duration | Found | Reconciled
- [ ] If no data in range: "No stock check data in this range for this studio."
- [ ] Error state: inline retry link

### Client-Side Behavior
- [ ] Client-side cache keyed by `(tab, range)`; cache is invalidated on range change and re-populated on tab switch
- [ ] Chart instances tracked; previous instance destroyed before re-rendering to prevent "canvas already in use" errors
- [ ] Chart.js loaded asynchronously; `_whenChart()` polls every 50ms (up to 2s) before giving up — handles CDN load race with IIFE init

---

## HQ Studios (`/hq/?section=studios`)

### Search
- [ ] Search input at top, autofocused on section load
- [ ] Typing filters the studios table in real-time by store name or number
- [ ] If 1-5 matches remain, a dropdown appears below the search input showing matching studios
- [ ] Clicking a dropdown item opens that studio's profile
- [ ] Dropdown hides when query has 0 matches or more than 5

### Studios Table

> **⚠️ Updated in sandbox:** Manager, Email, and Phone columns removed from the table; Region column added. See Sandbox Changes section for detail.

- [ ] Table with columns: Count (status dot) | Studio | Region
- [ ] Status dot colors: green (Updated), red (Discrepancy Detected), gray (Incomplete), hollow/unknown (no data)
- [ ] Status dots are driven by `reconcile.py` / `run_reconciliation()` — same source as the old Dashboard
- [ ] Studio and Region columns are sortable by clicking headers
- [ ] Region shows dash (—) if not populated
- [ ] Clicking a row opens that studio's profile panel
- [ ] "+ Add Studio" button at top right of search row opens the Add Studio modal

### Add Studio Modal
- [ ] Modal with three fields: Studio Number (text, 1–4 digits, leading zeros preserved), Studio Name (text, max 100 chars), Region (dropdown, 5 options)
- [ ] Client-side validation: all fields required, studio number matches `/^[0-9]{1,4}$/`, name max 100 chars, region must be one of the 5 valid values
- [ ] Inline field-level error messages on validation failure; modal stays open
- [ ] Submit POSTs to `POST /hq/studios/add`
- [ ] Server-side validation: same rules as client-side, plus uniqueness check on store_id
- [ ] On duplicate store_id, server returns error; displayed inline in modal without closing
- [ ] On success: modal closes, page reloads to Studios section, success toast appears (via sessionStorage handoff across reload)
- [ ] New studio can immediately log in to the Studio portal with store number as both username and password

### Studio Profile Panel
- [ ] Appears above the table when a studio is selected
- [ ] Header shows studio name + status dot + EDIT button
- [ ] Left column displays: Count Status (dot + text), Assigned SKUs, Discrepancies, Net Discrepancy
- [ ] Right column displays: Local Time (in store's timezone), Manager, Email, Phone
- [ ] Local time updates every 60 seconds while profile is open

> **⚠️ Updated in sandbox:** The Studio Analytics subsection (compliance rate, sparkline bar chart, frequently discrepant SKUs) was removed from the profile panel in Phase 2a of the HQ Analytics replacement. `buildStoreAnalytics()` and `renderSparkline()` were deleted from `hq_shell.html`. The left column now shows reconciliation-derived data only (status dot, assigned SKUs, discrepancy counts from `reconcile.py`).

### Edit Mode
- [ ] Clicking EDIT switches the profile to edit mode
- [ ] Manager, Email, Phone fields become editable text inputs
- [ ] Authentication section appears with: Username, New Password, Confirm Password fields
- [ ] SAVE and CANCEL buttons replace the EDIT button
- [ ] A save status message area appears next to the buttons
- [ ] Clicking CANCEL exits edit mode and re-renders the view profile
- [ ] Clicking SAVE posts to `/hq/studios/update-store` with JSON payload
- [ ] If passwords don't match, server returns error message displayed in status area
- [ ] On success, status shows "Saved." in green, then auto-returns to view mode after 800ms
- [ ] On error, status shows the error message in red
- [ ] On network failure, status shows "Network error" in red
- [ ] Saved data updates the local in-memory store data (no full page reload needed)

---

## HQ Files (`/hq/upload`)

### Header
- [ ] Same header layout as SPA shell
- [ ] FILES link shows as current/active
- [ ] REFRESH link reloads the page
- [ ] Section nav links (ANALYTICS, DATABASE, STUDIOS) navigate to the SPA

### Flash Messages
- [ ] Success messages displayed in green-styled banner
- [ ] Error messages displayed in standard warning banner

### Upload Section
- [ ] File input accepting `.csv` files, supports multiple file selection
- [ ] UPLOAD button submits the form
- [ ] RETURN TO DASHBOARD link navigates back to `/hq/`
- [ ] On successful upload, flash message shows count and filenames of uploaded files
- [ ] Recognized files (SKU list, variance, audit trail) are classified automatically by filename pattern
- [ ] If a file of the same name/type already exists, the old version is archived before overwriting

### File Table
- [ ] Only shown if files exist in `/input/`
- [ ] If no files exist, shows "No files found in /input/."
- [ ] Global files (SKU list, audit trail, other) listed first
- [ ] Variance files listed after a horizontal separator line
- [ ] Columns: File Name | Last Modified | Size | Actions
- [ ] File Name, Last Modified, and Size columns are sortable by clicking headers

### File Filtering
- [ ] Filter dropdown: All / SKU List / Audit Trail / Variance
- [ ] Selecting a filter shows only files of that type

### File Sorting
- [ ] Sort dropdown: Name A-Z / Name Z-A / Date Newest / Date Oldest / Size Largest / Size Smallest
- [ ] Selecting a sort option reorders the file rows accordingly

### File Actions (per row)
- [ ] DOWNLOAD link downloads the individual file
- [ ] DELETE button deletes the file after a browser confirmation dialog ("Delete [filename]?")
- [ ] Path traversal is blocked (filenames with `/` or `..` are rejected)

### Bulk Operations
- [ ] SELECT FILES button toggles checkbox visibility on each file row
- [ ] In select mode, button text changes to "CANCEL SELECT"
- [ ] Select-all checkbox in the header checks/unchecks all file checkboxes
- [ ] Exiting select mode unchecks all checkboxes
- [ ] DELETE ALL button deletes all files after confirmation ("Delete all files?")
- [ ] Flash message shows count of deleted files

### Bulk Download & Delete (when files are selected)
- [ ] Download selected: creates a ZIP file named `STUDS_files_YYYYMMDD_HHMMSS.zip` containing the selected files
- [ ] Delete selected: deletes only the checked files, shows count in flash message

### OmniCounts File Generator (on Files page)
- [ ] Form with file input (accepts `.csv`), store number text field, and GENERATE button
- [ ] Store number validated client-side (digits only) and server-side
- [ ] Upload a Brightpearl full inventory summary CSV
- [ ] Filters uploaded CSV to only SKUs present in the current weekly SKU list (via `scan_input_files()` and `load_sku_list()`)
- [ ] RS-prefixed SKUs are excluded
- [ ] Missing SKUs (in weekly list but not in CSV) are appended as placeholder rows with `0` for numeric columns and descriptions from `SKU_Master.csv`
- [ ] Returns a download named `{store_number}_OnHands.csv`
- [ ] Flash error if no weekly SKU list file exists in `/input/`
- [ ] Flash error if uploaded CSV has no SKU column

---

## HQ Database (`/hq/?section=database`)

### Master SKU File Section
- [ ] Displays: filename (SKU_Master.csv), SKU count, last updated timestamp
- [ ] File upload input accepts `.csv` files
- [ ] UPLOAD button submits the new master file
- [ ] Old master file is archived before overwrite
- [ ] After upload, image/SKU audit runs automatically
- [ ] Flash message confirms update with count of SKUs added and removed

### SKU Status File Section
- [ ] Positioned below Master SKU File and above Product Images
- [ ] Displays: filename (SKU_Status.csv), SKU count, last updated timestamp (or dash if not present)
- [ ] File upload input accepts `.csv` files
- [ ] UPLOAD button submits the new status file
- [ ] Old status file is archived before overwrite (file_type 'sku_status')
- [ ] Flash message confirms update with count of SKUs loaded
- [ ] Expected upload filename pattern: SKU_STATUS_MM.DD.YY.csv
- [ ] Canonical storage path: /database/master/SKU_Status.csv
- [ ] Expected columns: sku, status (values: "active" or "sunset", case-insensitive)

### SKU Prices File Section
- [ ] Positioned below SKU Status File and above Product Images
- [ ] Displays: filename (SKU_Prices.csv), SKU count, last updated timestamp (or dash if not present)
- [ ] File upload input accepts `.csv` files
- [ ] UPLOAD button submits the new prices file
- [ ] Old prices file is archived before overwrite (file_type 'sku_prices')
- [ ] Flash message confirms update with count of SKUs loaded
- [ ] Canonical storage path: /database/SKU_Prices.csv
- [ ] Expected columns: sku, retail_price (decimal number, no currency symbol)

### Product Images Section
- [ ] Displays count of images in `/database/images/`
- [ ] File upload input accepts `.jpg, .jpeg, .png, .webp`, supports multiple files
- [ ] UPLOAD button submits the images
- [ ] After upload, image/SKU audit runs automatically
- [ ] Flash message confirms count of images uploaded

### Image/SKU Audit Section
- [ ] Displays summary: X orphaned images, Y SKUs missing images
- [ ] If all matched: "All SKUs and images are matched."

### Orphaned Images Table (if any)
- [ ] Columns: Preview (thumbnail) | Filename | Assign to SKU | Actions
- [ ] Preview shows the actual image from `/database/images/`
- [ ] Each row has a text input for a SKU and an ASSIGN button
- [ ] Assigning renames the image file to `[SKU].[ext]` and marks the flag as resolved
- [ ] Each row has a DISCONTINUE button that marks the flag as discontinued
- [ ] After assign or discontinue, audit re-runs and page redirects

### Missing Images Table (if any)
- [ ] Columns: SKU | Description | Status
- [ ] Status shows "No image on file" for each

---

## HQ Settings

### Settings Hub (`/hq/settings`)
- [ ] Displays two navigation cards with arrow indicators
- [ ] "Login Credentials" card links to `/hq/settings/credentials`
- [ ] "Email Settings" card links to `/hq/settings/email`

### Login Credentials (`/hq/settings/credentials`)
- [ ] Table with one row per studio (41 real studios; count grows as studios are added via the Add Studio modal)
- [ ] Each row shows: Store name, Username input, Password input
- [ ] Username inputs are pre-populated with current values
- [ ] Password inputs are blank with placeholder "Leave blank to keep"
- [ ] SAVE button submits the form
- [ ] Only non-empty username fields are updated
- [ ] Only non-empty password fields are updated (hashed with bcrypt)
- [ ] Flash message: "Credentials updated." or "No changes made."
- [ ] Redirects back to the same page after save

### Email Settings (`/hq/settings/email`)
- [ ] Email template textarea for customizing the email body
- [ ] Help text explains `{{sku_table}}` placeholder usage
- [ ] Table with one row per studio for setting email addresses
- [ ] Each row shows: Store name, Email input (placeholder shows default format)
- [ ] SAVE button submits the form
- [ ] Saves email template and all per-store emails to settings.json
- [ ] Flash message: "Email settings saved."
- [ ] Redirects back to the same page after save

---

## HQ Archive (`/hq/archive`)

- [ ] Displays last 50 archived files sorted by most recent first
- [ ] Table columns: File Type | Original Filename | Store | Archived At | Row Count | Size
- [ ] Archives are created automatically when files are overwritten (MSF uploads, input file uploads)

---

## Studio Portal (`/studio/`)

### Header
- [ ] Left nav box (lime): LOGOUT (or HQ | LOGOUT if admin user)
- [ ] Center: STUDS logo with "(CONFIDENTIAL)"
- [ ] Right nav box (lavender): OMNICOUNTS | PRINT (PRINT only shown if SKU list exists)
- [ ] SKU list filename displayed below header

### BEGIN COUNT Button
- [ ] Lime (#c8f135) bold uppercase button labeled "BEGIN COUNT"
- [ ] Positioned in the content row below the header, right-aligned, same row as search input
- [ ] Navigates to `/studio/tutorial`
- [ ] Only visible when SKU list exists (inside studio-main)

### Empty State
- [ ] If no SKU list file exists, displays a message indicating no active SKU list

### Search
- [ ] Search input field filters SKU cards in real-time
- [ ] Filters by SKU code or description (case-insensitive)
- [ ] Displays count of visible/matching SKUs, updates dynamically

### SKU Card Grid
- [ ] Responsive grid layout of product cards
- [ ] Each card shows: product image (or "No image" placeholder), SKU code, description, barcode
- [ ] Images are loaded from `/database/images/` matching the SKU prefix (case-insensitive)
- [ ] Barcodes generated client-side using JsBarcode (CODE128 format, 28px height, no text)
- [ ] Cards have data attributes for SKU and description for search filtering

### SKU Status Tags
- [ ] Each SKU card displays a status tag in the top-right corner of the image area (if status is known)
- [ ] Status data loaded from /database/master/SKU_Status.csv via `load_sku_status()`
- [ ] ACTIVE tag: lavender (#e8b4f8) background, black text, label "ACTIVE"
- [ ] SUNSET tag: lime (#c8f135) background, black text, label "SUNSET"
- [ ] No tag rendered if SKU is not in the status file or status is not active/sunset
- [ ] Tags use CSS classes: `.studio-sku-tag`, `.studio-sku-tag-active`, `.studio-sku-tag-sunset`

### Retail Price on Cards
- [ ] Each SKU card displays the retail price right-aligned in the text area, opposite the SKU/description
- [ ] Price data loaded from /database/SKU_Prices.csv via `load_sku_prices()`
- [ ] File columns: sku, retail_price (decimal number, no currency symbol)
- [ ] Format: "$XX.XX" with dollar sign and two decimal places
- [ ] If SKU is not in the price file, no price is rendered
- [ ] SKU lookup is case-insensitive (uppercased for matching)
- [ ] CSS class: `.studio-sku-price` (bold, 14px, black)
- [ ] Card info area uses flex layout (`.studio-card-info`) to align SKU/desc left and price right

### Print Functionality
- [ ] If no search is active, clicking PRINT immediately calls `window.print()`
- [ ] If a search filter is active, clicking PRINT opens a print options modal
- [ ] Modal offers two options: "PRINT ALL [X] SKUS" and "PRINT [X] MATCHING SKUS"
- [ ] Print All temporarily shows all cards, prints, then restores filter
- [ ] Print Filtered prints only the currently visible cards
- [ ] Cancel link closes the modal
- [ ] Clicking outside the modal closes it
- [ ] Print-specific stylesheet shows a "STUDS" header visible only on paper

### Begin Count / Tutorial Page (`/studio/tutorial`)

> **⚠️ Rebuilt in sandbox:** This flow was replaced from a 9-step static instructional tutorial (no persistence, no uploads) with a 7-step functional stock count wizard backed by Flask session storage. See the Sandbox Changes section at the bottom of this document for full detail.
>
> **Begin Count is THE stock check workflow for the network.** The old Start Your Stock Check flow remains in the codebase but is deprecated and no longer supported by HQ Analytics.

#### Navigation & Shell
- [ ] On Studio main page: lime BEGIN COUNT button in content row (right of search bar), navigates to `/studio/tutorial`
- [ ] On OmniCounts page: BEGIN COUNT navlink in header nav (lavender, left of STUDIO link)
- [ ] Header matches Studio sub-page layout (left: HQ/LOGOUT, center: STUDS logo, right: STUDIO link back)
- [ ] Sub-header label shows "BEGIN COUNT"
- [ ] Single-page multi-step flow; one step visible at a time
- [ ] Step indicator bar (numbered 1–7) appears at top of wizard once intro is passed; hidden on intro screen
- [ ] Completed steps are clickable in the step indicator for backward and forward navigation
- [ ] Current step highlighted; locked/future steps greyed out and non-clickable

#### Intro Screen
- [ ] Heading: "Hey, Stud!" — centered, font ~15–20% larger than base body size
- [ ] Required "Your name" text field above the checklist; advance button disabled until field is non-empty (trimmed)
- [ ] Four-item checkbox checklist (visual only, no state tracked)
- [ ] Begin button calls `beginStockCheck()`: saves name via POST /studio/tutorial/counter-name, then navigates to Step 1
- [ ] Intro screen not shown again once step > 0 (resume-on-return behavior)

#### Session & Persistence
- [ ] Step tracked in `session['begin_count_step']` (0 = intro); page resumes at current step on reload
- [ ] Browser-close / session-expiry resets to intro (Flask default session cookies)
- [ ] Start timestamp captured exactly once on step 0→1 transition (`session['begin_count_started_at']`, ISO 8601 UTC)
- [ ] Completion flags tracked for steps without upload-based signals: `begin_count_step2_done`, `begin_count_step3_done`, `begin_count_step5_done`, `begin_count_step6_done`
- [ ] Counter name stored in `session['begin_count_counter_name']`
- [ ] POST /studio/tutorial/step updates `session['begin_count_step']`; sets done flags on forward advance
- [ ] Analytics run ID stored in `session['begin_count_run_id']` (integer FK to `stock_checks.id`); cleared on reset

#### Step 1 — Brightpearl Upload
- [ ] Drag-and-drop or click-to-browse file upload for Brightpearl Inventory Summary CSV
- [ ] Auto-uploads on file selection; color-coded states (idle / uploading / success / error)
- [ ] On success: parses CSV, stores `session['begin_count_bp_onhand']` (uppercase SKU keys) and `session['begin_count_bp_filename']`
- [ ] Advance button gated: enabled only after successful upload
- [ ] Route: POST /studio/tutorial/upload-bp
- [ ] Re-uploading recomputes downstream variance table on next page load

#### Step 2 — QR Code Scan
- [ ] Displays QR code image for the current studio (from `static/qr/studio_{id}.png`)
- [ ] Fallback message shown for studios without a QR code configured
- [ ] Instructional-only; step marked complete when user advances

#### Step 3 — SKU Reference Grid
- [ ] Read-only 5-across SKU card grid mirroring the Studio main page layout
- [ ] Built using the same helpers (scan_input_files, load_master_skus, load_sku_status, etc.)
- [ ] Includes real-time search/filter input
- [ ] Instructional-only; step marked complete when user advances

#### Step 4 — OmniCounts Upload & Variance Table
- [ ] Drag-and-drop or click-to-browse file upload for OmniCounts Count Report CSV
- [ ] Auto-uploads; detects SKU + counted columns, sums per SKU, filters to assigned SKUs
- [ ] Stores `session['begin_count_oc_counted']` and `session['begin_count_oc_filename']`
- [ ] Route: POST /studio/tutorial/upload-oc
- [ ] Advance button gated on successful upload
- [ ] Variance table columns: SKU | Product Name | On-Hand | Counted (editable) | Variance
- [ ] Variance formula: Counted − On-Hand
- [ ] Variance color: green (positive/overage), red (negative/shortage), neutral (zero)
- [ ] Edits to Counted field trigger debounced (600ms) fire-and-forget POST /studio/tutorial/variance/update; persists each change to `session['begin_count_oc_counted']`
- [ ] Re-uploading OC file overwrites counted data; re-uploading Step 1 file does NOT wipe OC data

#### Steps 5 & 6 — Instructional Screens
- [ ] Step 5: Check for major variances — instructional-only, advance button present
- [ ] Step 6: Make adjustments in Brightpearl — instructional-only, advance button present
- [ ] Advancing from either sets the corresponding done flag in session

#### Step 7 — Crosscheck & Completion
- [ ] Drag-and-drop or click-to-browse file upload for fresh post-adjustment Brightpearl CSV
- [ ] Route: POST /studio/tutorial/upload-bp-verify
- [ ] Stores `session['begin_count_bp_verify_onhand']` and `session['begin_count_bp_verify_filename']`
- [ ] Upload blocked if no `begin_count_oc_counted` in session
- [ ] Crosscheck table columns: SKU | Product Name | New On-Hand | Final Counted | Status (✅ match / ❌ still off)
- [ ] Completion banner: green "All adjustments have been verified. Great work." when still_off == 0; amber "Some variances still need attention — see the crosscheck table above for details." when still_off > 0
- [ ] Summary block: Completed by (counter name), Total SKUs checked, Variances reconciled, Variances still off, Step 1 / Step 4 / Step 7 filenames, Completion timestamp, Duration
- [ ] Duration formatted by `format_duration(seconds)` in app.py: `"<1m"` / `"{n}m"` / `"{h}h {n}m"`
- [ ] "Back to Dashboard" button returns to `/studio/`
- [ ] "Start a new Stock Check" secondary button triggers browser confirm dialog then POST /studio/tutorial/reset, which clears all 14 `begin_count_*` session keys and redirects to `/studio/tutorial`

### OmniCounts Page (`/studio/omnicounts`)
- [ ] Dedicated page accessible via OMNICOUNTS navlink in the Studio header (lavender button, left of PRINT)
- [ ] OMNICOUNTS navlink is always visible (not conditional on SKU list existence)
- [ ] Header matches Studio main page layout (left: HQ/LOGOUT, center: STUDS logo, right: STUDIO link back)
- [ ] Sub-header label shows "OMNICOUNTS" instead of "STUDIO"
- [ ] Form with file input (accepts `.csv`), store number text field, and GENERATE button
- [ ] Store number validated client-side (digits only) and server-side
- [ ] Upload a Brightpearl full inventory summary CSV
- [ ] Filters uploaded CSV to only SKUs present in the current weekly SKU list (via `scan_input_files()` and `load_sku_list()`)
- [ ] RS-prefixed SKUs are excluded
- [ ] Missing SKUs (in weekly list but not in CSV) are appended as placeholder rows with `0` for numeric columns and descriptions from `SKU_Master.csv`
- [ ] Returns a download named `{store_number}_OnHands.csv`
- [ ] Flash error if no weekly SKU list file exists in `/input/`
- [ ] Flash error if uploaded CSV has no SKU column
- [ ] Generation logic is identical to the HQ version (shared helper function)

---

## Reconciliation Logic (observable effects)

- [ ] SKUs with RS prefix are excluded from all reconciliation
- [ ] Variance files must contain columns: Sku, Description, Counted Units, Onhand Units, Unit Variance
- [ ] Audit trail entries are matched by warehouse ID (numeric prefix, zero-padded to 3 digits)
- [ ] Only audit trail rows with reference containing "stock update" or "stock check" (case-insensitive) count as actual pushes
- [ ] Required push = Unit Variance from variance file
- [ ] Actual push = sum of matching audit trail quantities for that SKU and store
- [ ] Discrepancy = Required Push - Actual Push
- [ ] Store status: "Updated" if zero discrepancies, "Discrepancy Detected" if any non-zero
- [ ] Stores without a variance file get "Incomplete (missing file)"
- [ ] Stores with unrecognized variance file schema get "Incomplete (unrecognized file format)"
- [ ] Multiple SKU lists: most recent (by filename date) is used, warning shown
- [ ] Multiple audit trails: most recent (by filename date) is used, warning shown
- [ ] Store list always includes all seeded stores from database (41 real studios in sandbox), regardless of file presence

---

## Global Behaviors

### Column Sorting (all tables app-wide)
- [ ] Sortable columns indicated by clickable headers
- [ ] Supports data types: string (case-insensitive), number (parses floats), percent (strips %)
- [ ] First click sorts ascending, second click sorts descending, toggles on repeat
- [ ] Sort direction indicator arrow (up/down unicode) appended to active column header
- [ ] Previous sort indicators are removed when sorting a different column

### Context Processor (all pages)
- [ ] `current_user_name` injected into all templates (from session display_name)
- [ ] `last_loaded_global` timestamp injected into all templates

### Image Serving
- [ ] Product images served from `/database/images/<filename>` (no authentication required)

---

## Deployment

### STUDS_DATA_DIR Environment Variable
- [ ] If `STUDS_DATA_DIR` is set, all mutable data directories are rooted under it:
  - `INPUT_DIR` → `$STUDS_DATA_DIR/input/`
  - `DATABASE_DIR` → `$STUDS_DATA_DIR/database/`
  - `MASTER_DIR` → `$STUDS_DATA_DIR/database/master/`
  - `IMAGES_DIR` → `$STUDS_DATA_DIR/database/images/`
  - `PROCESSED_DIR` → `$STUDS_DATA_DIR/processed/`
  - `STORE_DB` → `$STUDS_DATA_DIR/database/store_profiles.db`
  - `ARCHIVE_DB` → `$STUDS_DATA_DIR/database/archive.db`
- [ ] If `STUDS_DATA_DIR` is not set, all paths fall back to repo root (local development default)
- [ ] `SETTINGS_FILE` always stays at the repo root regardless of `STUDS_DATA_DIR`
- [ ] On startup (`__main__`), `INPUT_DIR`, `PROCESSED_DIR`, `DATABASE_DIR`, `MASTER_DIR`, and `IMAGES_DIR` are created if they don't exist
- [ ] Purpose: allows Railway (or similar) to mount a single persistent volume at `STUDS_DATA_DIR` containing all mutable state

---

## Sandbox Changes

> Changes made in the active development session. Items are organized by feature area. The Start Your Stock Check flow (`/studio/stock-check/*`, `templates/stock_check.html`, `stock_check_count.html`, `stock_check_verify.html`) and its session keys (`bp_onhand`, `sc_counts`, `post_bp_onhand`, etc.) were not touched in any phase of this work. **This flow is now deprecated** — it is no longer supported by HQ Analytics and should be considered legacy code. Begin Count is the sole active stock check workflow.

---

### Begin Count Wizard Rebuild — Phases 1–5

**Summary:** Replaced the old 9-step static instructional tutorial (no uploads, no persistence, no data processing) with a fully functional 7-step stock count wizard backed by Flask session storage.

**Files touched:** `app.py`, `templates/studio_tutorial.html`

**Routes added:**

| Route | Method | Purpose |
|---|---|---|
| `POST /studio/tutorial/step` | POST | Updates `session['begin_count_step']`; sets done flags on forward advance; captures start timestamp on first 0→1 transition |
| `POST /studio/tutorial/upload-bp` | POST | Parses Brightpearl CSV → `begin_count_bp_onhand` (uppercase keys), `begin_count_bp_filename` |
| `POST /studio/tutorial/upload-oc` | POST | Parses OmniCounts CSV → `begin_count_oc_counted`, `begin_count_oc_filename` |
| `POST /studio/tutorial/variance/update` | POST | Persists a single-SKU Counted edit to `begin_count_oc_counted`; sets `session.modified = True` |
| `POST /studio/tutorial/upload-bp-verify` | POST | Parses post-adjustment BP CSV → `begin_count_bp_verify_onhand`, `begin_count_bp_verify_filename`; returns crosscheck_rows + summary JSON (includes counter_name, duration, completed_at) |
| `POST /studio/tutorial/counter-name` | POST | Validates (1–100 chars, stripped) and stores `begin_count_counter_name` |
| `POST /studio/tutorial/reset` | POST | Clears all 14 `begin_count_*` session keys; redirects to `/studio/tutorial` |

**`GET /studio/tutorial` additions:** builds `step_status` list (completed/current/locked per step), `variance_rows` (rebuilt from `begin_count_bp_onhand` + `begin_count_oc_counted` on every load), `crosscheck_rows` (rebuilt from `begin_count_bp_verify_onhand` + `begin_count_oc_counted` on every load), `summary` dict (counter_name, duration via `_resume_duration`), and `counter_name` for intro field pre-fill.

**Session keys (all `begin_count_*` prefix):**

| Key | Type | Set by | Description |
|---|---|---|---|
| `begin_count_step` | int | POST /tutorial/step | Current wizard step (0 = intro) |
| `begin_count_started_at` | str (ISO 8601 UTC) | POST /tutorial/step | Start timestamp; captured once on 0→1 |
| `begin_count_bp_onhand` | dict | POST /tutorial/upload-bp | On-hand quantities keyed by uppercase SKU |
| `begin_count_bp_filename` | str | POST /tutorial/upload-bp | Original BP upload filename |
| `begin_count_oc_counted` | dict | POST /tutorial/upload-oc | Counted quantities keyed by uppercase SKU |
| `begin_count_oc_filename` | str | POST /tutorial/upload-oc | Original OC upload filename |
| `begin_count_bp_verify_onhand` | dict | POST /tutorial/upload-bp-verify | Post-adjustment BP on-hand quantities |
| `begin_count_bp_verify_filename` | str | POST /tutorial/upload-bp-verify | Post-adjustment BP upload filename |
| `begin_count_step2_done` | bool | POST /tutorial/step | Step 2 completion flag |
| `begin_count_step3_done` | bool | POST /tutorial/step | Step 3 completion flag |
| `begin_count_step5_done` | bool | POST /tutorial/step | Step 5 completion flag |
| `begin_count_step6_done` | bool | POST /tutorial/step | Step 6 completion flag |
| `begin_count_counter_name` | str | POST /tutorial/counter-name | Counter's name from intro screen |
| `begin_count_run_id` | int | POST /tutorial/step (0→1) | FK to `stock_checks.id`; written by the analytics persistence layer |

**`app.py` helpers added:**
- `format_duration(seconds)` — returns `"<1m"` / `"{n}m"` / `"{h}h {n}m"`
- `_resume_duration(sess)` — reads `begin_count_started_at` from session, computes elapsed seconds, returns formatted string

**Step-by-step breakdown:**

- **Intro:** "Hey, Stud!" heading (centered, ~15–20% larger font), required name field, four-item visual checklist, advance button gated on non-empty name + all checklist conditions
- **Step 1:** BP CSV upload → on-hand dict stored in session; advance gated on success
- **Step 2:** QR code display from `static/qr/studio_{id}.png`; fallback for unconfigured studios
- **Step 3:** Read-only 5-across SKU grid with search filter, using same helpers as Studio main page
- **Step 4:** OC CSV upload → variance table (SKU / Product Name / On-Hand / Counted / Variance); Counted column is editable, debounced 600ms persist; green for overage, red for shortage, neutral for zero; advance gated on successful upload
- **Steps 5 & 6:** Instructional-only screens with advance buttons; advancing sets done flags
- **Step 7:** BP-verify upload → crosscheck table (SKU / Product Name / New On-Hand / Final Counted / ✅/❌ Status); adaptive completion banner (green all-clear vs. amber still-off); summary block (name, timestamps, duration, filenames, counts)

---

### Step Indicator & Navigation

**What was built:** Numbered step indicator (1–7) at the top of the wizard. Hidden on intro screen. Clickable nodes for completed steps; current step highlighted; locked/future nodes non-clickable.

**Key behaviors:**
- `goToStep(id)` updates `stepDoneMap` and `currentClientStep`, then calls `updateStepIndicator()`
- `onIndicatorNodeClick(stepNum)` navigates only if `stepDoneMap[stepNum]` is true
- Line segments between nodes color to reflect completion state
- Step status list (`step_status`) is server-rendered into `stepStatusFromSvr` JS variable on every page load

**Files touched:** `app.py` (step_status construction in GET /studio/tutorial), `templates/studio_tutorial.html` (`#step-indicator` HTML block + `updateStepIndicator()` / `onIndicatorNodeClick()` JS functions)

---

### Reset Button

**What was built:** A "Start a new Stock Check" secondary button on the Step 7 completion screen. Requires browser `confirm()` before firing.

- Route: `POST /studio/tutorial/reset`
- Clears all 14 `begin_count_*` session keys (including `begin_count_run_id`)
- Redirects to `/studio/tutorial` (intro screen)

**Files touched:** `app.py`, `templates/studio_tutorial.html`

---

### Counter Name Entry

**What was built:** Required "Your name" text input on the intro screen. Stored in session and displayed in the Step 7 summary as "Completed by: ...". Advance button gated on non-empty trimmed value.

- Route: `POST /studio/tutorial/counter-name`
- Session key: `begin_count_counter_name`
- Validation: 1–100 characters after stripping whitespace
- Cleared on reset

**Files touched:** `app.py`, `templates/studio_tutorial.html`

---

### Duration Tracking

**What was built:** Server-side elapsed time from first step to Step 7 completion. Start timestamp captured exactly once; formatted at render time.

- Session key: `begin_count_started_at` (ISO 8601 UTC)
- Guard: re-entering the intro (e.g., re-navigating to step 0) does not reset the timestamp if it is already set
- `format_duration(seconds)` helper in `app.py`: `"<1m"` (< 60s) / `"{n}m"` (< 1h) / `"{h}h {n}m"` (≥ 1h)
- `_resume_duration(sess)` computes elapsed from stored timestamp to `datetime.now(timezone.utc)`
- Duration rendered in Step 7 summary block (always visible row, never `display:none`)
- Cleared on reset

**Files touched:** `app.py`, `templates/studio_tutorial.html`

---

### HQ Studios Management

> All changes in this subsection are scoped to the HQ portal studios section. No Begin Count files, no Start Your Stock Check files, no `hq_shell.html` profile panel, no `reconcile.py`, and no existing HQ credentials routes were modified.

---

#### Real Studios List Replacement

**What was built:** The 40-entry dummy `SEED_STORES` list (placeholder locations like "001 NY SoHo") was replaced with the real 41-studio Studs list. A one-time startup data migration detects and replaces dummy rows.

**`SEED_STORES` in `app.py`:** Now holds the real 41 studios as `(store_id, name, 'America/New_York')` tuples. Timezone is `America/New_York` for all entries — accurate per-region timezone mapping is deferred to future work. Store number gaps (003–005, 013) are intentional and preserved.

**`REAL_STUDIOS` in `app.py`:** Parallel list of `(store_id, name, region)` tuples carrying the region data. `SEED_STORES` doesn't hold region because the DB schema migration must add the `region` column before this data can be inserted.

**`VALID_REGIONS` in `app.py`:** Python set of the five valid region strings used for server-side validation:
- `NY & East Coast Metro`
- `North Pacific`
- `Southeast`
- `South Central`
- `Northeast & Central`

**`migrate_to_real_studios(conn)` in `app.py`:** Called from `init_store_db()` on every app startup after all schema migrations have run.
- Detects dummy data by checking `SELECT 1 FROM stores WHERE name = '001 NY SoHo'`
- If found: `DELETE FROM stores`, then reinserts all 41 real studios from `REAL_STUDIOS` with fresh bcrypt-hashed credentials (`username = password = store_id`)
- Idempotent: if the canary row is absent (real data already in place), returns immediately
- Must run after the `region` column migration so the INSERT can include region values

**Files touched:** `app.py`

---

#### Region Column — Schema Migration

**What was built:** A new `region TEXT DEFAULT ''` column on the `stores` table.

**Migration:** Added to `init_store_db()` following the exact existing pattern used for `manager` and `phone`:
```python
if 'region' not in existing:
    conn.execute("ALTER TABLE stores ADD COLUMN region TEXT DEFAULT ''")
```
Runs before `migrate_to_real_studios()` so region values can be written during the data migration.

**Files touched:** `app.py`

---

#### HQ Studios Page Table — Column Changes

**What was built:** The main studios table display was updated. The Studio Profile Panel edit form was **not** modified.

**Columns removed from table display only:** Manager, Email, Phone. These three fields remain in the `stores` table schema and remain editable in the Studio Profile Panel via `enterEditMode` → `POST /hq/studios/update-store`. No change to that flow.

**Column added:** Region (`store.region`, right after Studio). Shows `—` if empty.

**Final column order:** Count (status dot) | Studio | Region

**Sortable columns:** Studio (col index 1), Region (col index 2). Uses the `sortable_th` macro, matching existing table conventions.

**Files touched:** `templates/fragments/studios.html`

---

#### Add Studio Modal + Route

**What was built:** A `+ Add Studio` button on the HQ studios page that opens a form modal for creating a new studio entry.

**Button placement:** Flex row alongside the search input, right-aligned (`flex-shrink: 0`).

**Modal fields:**

| Field | Input | Validation |
|---|---|---|
| Studio Number | Text, maxlength 4 | Required; `/^[0-9]{1,4}$/` — digits only, leading zeros preserved (`"046"` stores as `"046"`) |
| Studio Name | Text, maxlength 100 | Required; max 100 chars |
| Region | Select (5 options) | Required; must match one of the 5 `VALID_REGIONS` strings exactly |

**Client-side validation:** Fires on submit; inline error messages appear below each offending field; modal stays open on failure.

**Server errors** (including duplicate `store_id`) returned as `{"ok": false, "error": "..."}` HTTP 400, displayed inline in the modal without closing it.

**Success flow:**
1. Modal closes
2. `sessionStorage.setItem('studioAdded', store_id)` saves the message across the reload
3. `window.location.href = '/hq/?section=studios'` — full page reload (refreshes `storeDataGlobal` in `hq_shell.html`)
4. On load, the fragment's inline `<script>` reads sessionStorage, shows a lime toast for 4 seconds, clears the key

**Route: `POST /hq/studios/add`** (new)

Server validates: `store_id` non-empty and `/^[0-9]{1,4}$/`; `name` non-empty and ≤ 100 chars; `region` in `VALID_REGIONS`; `store_id` not already in `stores` table.

On success, INSERTs:

| Column | Value |
|---|---|
| `store_id` | submitted (as-is, leading zeros preserved) |
| `name` | submitted (trimmed) |
| `timezone` | `'America/New_York'` |
| `username` | `store_id` |
| `password_hash` | `bcrypt.hashpw(store_id.encode(), bcrypt.gensalt())` |
| `email`, `manager`, `phone` | `''` (empty defaults) |
| `region` | submitted |

Returns `{"ok": true, "store_id": "..."}` on success.

**New helper `get_store_by_id_db(store_id)`:** Looks up a store by primary key; returns dict or None.

**Studio login for new studios:** The existing `POST /studio/login` route uses `get_store_by_username(username)` then bcrypt-checks the password. Since `username = store_id` and `password_hash = bcrypt(store_id)`, a newly added studio can immediately log in with their store number as both username and password — no separate credential setup step required.

**Files touched:** `app.py`, `templates/fragments/studios.html`

---

### Stock Check Persistence Layer (Phase 1)

**Summary:** Added two new SQLite tables to `store_profiles.db` and seven write-hook helper functions. Every Begin Count run now creates a persistent record that feeds HQ Analytics. All DB writes are fire-and-forget (wrapped in `try/except`, errors printed to `stderr`, never break the user's flow).

**Files touched:** `app.py`, `analytics_begin_count.py` (new module, Phase 2a)

#### New Tables

**`stock_checks`** — one row per Begin Count run:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `store_id` | TEXT | FK to `stores.store_id` |
| `counter_name` | TEXT | From intro screen |
| `skulist_filename` | TEXT | Weekly SKU list filename |
| `week_identifier` | TEXT | `MM-DD-YY` parsed from SKU list filename |
| `started_at` | DATETIME | ISO 8601 UTC; set on step 0→1 |
| `completed_at` | DATETIME | Set on Step 7 upload-bp-verify |
| `duration_seconds` | INTEGER | Computed from started_at → completed_at |
| `status` | TEXT | `in_progress` / `completed` / `abandoned` |
| `furthest_step` | INTEGER | 1–7; bumped on each forward transition |
| `assigned_sku_count` | INTEGER | Count of SKUs in this run's SKU list |
| `total_variances` | INTEGER | Count of non-zero variance SKUs (Step 4) |
| `variances_reconciled` | INTEGER | Count of matched SKUs at Step 7 |
| `variances_still_off` | INTEGER | Count of unmatched SKUs at Step 7 |
| `bp_filename` | TEXT | Step 1 upload filename |
| `oc_filename` | TEXT | Step 4 upload filename |
| `bp_verify_filename` | TEXT | Step 7 upload filename |
| `created_at` | DATETIME | `CURRENT_TIMESTAMP` |
| `updated_at` | DATETIME | Updated on each write |

**`stock_check_skus`** — one row per assigned SKU per run:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `stock_check_id` | INTEGER | FK to `stock_checks.id` |
| `sku` | TEXT | Uppercase |
| `on_hand` | INTEGER | From Step 1 BP upload |
| `counted` | INTEGER | From Step 4 OC upload; updated by variance/update edits |
| `new_on_hand` | INTEGER | From Step 7 BP-verify upload |
| `final_counted` | INTEGER | From Step 4 session data at Step 7 finalization |
| `matched` | BOOLEAN | `1` if new_on_hand == final_counted |

Both tables are created by `init_store_db()` on app startup (idempotent).

#### Helper Functions (all in `app.py`)

| Function | Called from | What it writes |
|---|---|---|
| `create_stock_check_row(store_id, counter_name, skulist_filename, week_identifier, started_at)` | POST /tutorial/step (0→1) | INSERTs a new `stock_checks` row with `status='in_progress'`, `furthest_step=1`; returns the new `id` |
| `update_stock_check_row(run_id, **kwargs)` | Multiple hooks | UPDATEs specific columns; accepts any subset of columns as kwargs |
| `bump_furthest_step(run_id, step)` | POST /tutorial/step (forward advance), upload-bp-verify | Sets `furthest_step = MAX(current, step)` |
| `replace_stock_check_skus(run_id, skus_data)` | POST /tutorial/upload-oc | DELETEs all existing SKU rows for this run, then INSERTs fresh rows |
| `update_stock_check_sku_counted(run_id, sku, counted)` | POST /tutorial/variance/update | UPDATEs a single SKU's `counted` value |
| `finalize_stock_check_skus(run_id, verify_data)` | POST /tutorial/upload-bp-verify | UPDATEs each SKU row with `new_on_hand`, `final_counted`, `matched` |
| `mark_stock_check_abandoned(run_id)` | POST /tutorial/reset | Sets `status='abandoned'` WHERE `status != 'completed'` — completed runs are never overwritten |

**`parse_week_identifier(filename)`** helper: extracts the `MM-DD-YY` date from the SKU list filename pattern `SKU_LIST_MM.DD.YY.csv`; returns `None` if no match.

#### Wire-up into Begin Count Routes

| Route | Hook | Effect |
|---|---|---|
| POST /tutorial/step (step 0→1) | `create_stock_check_row(...)` | Creates the run row; stores returned `id` as `session['begin_count_run_id']` |
| POST /tutorial/step (any forward) | `bump_furthest_step(run_id, new_step)` | Advances the furthest_step marker |
| POST /tutorial/upload-bp | `update_stock_check_row(run_id, bp_filename=..., assigned_sku_count=..., skulist_filename=..., week_identifier=...)` | Records Step 1 metadata |
| POST /tutorial/upload-oc | `update_stock_check_row(run_id, oc_filename=..., total_variances=...)` + `replace_stock_check_skus(run_id, skus_data)` | Records Step 4 metadata and inserts SKU rows |
| POST /tutorial/variance/update | `update_stock_check_sku_counted(run_id, sku, qty)` | Persists inline Counted edits to the DB |
| POST /tutorial/upload-bp-verify | `update_stock_check_row(run_id, bp_verify_filename=..., variances_reconciled=..., variances_still_off=..., completed_at=..., duration_seconds=..., status='completed')` + `finalize_stock_check_skus(run_id, verify_data)` + `bump_furthest_step(run_id, 7)` | Marks run complete; finalizes SKU match data |
| POST /tutorial/reset | `mark_stock_check_abandoned(run_id)` | Marks run abandoned (no-op if already completed) |

---

### HQ Analytics Replacement (Phases 2a & 2b)

**Summary:** Deleted the old fake-data analytics module and its 6-panel UI; replaced with a real 3-tab analytics page backed by `stock_checks` / `stock_check_skus`. This is now THE analytics source for the entire HQ portal.

#### Phase 2a — Backend & Cleanup

**Deleted:**
- `analytics_data.py` — the old `random.seed(42)`-based fake data generator
- `templates/analytics.html` — an orphaned template (no longer referenced by any route)
- `templates/fragments/dashboard.html`'s `storeAnalytics` variable injection and `storeReconData` script injection (removed from `templates/fragments/studios.html`)
- `buildStoreAnalytics()` and `renderSparkline()` JS functions from `hq_shell.html`; all their call sites removed

**New module: `analytics_begin_count.py`**

Standalone module (no `from app import …` — avoids circular import). Uses its own `_get_db()` that mirrors `app.py`'s `get_db()` and reads `STUDS_DATA_DIR`.

| Helper | Route | Description |
|---|---|---|
| `get_analytics_overview(range_key)` | `GET /hq/analytics/overview` | Current-week headline stats + network-wide trend data |
| `get_analytics_participation(range_key)` | `GET /hq/analytics/participation` | Per-studio participation rows with weekly status arrays |
| `get_analytics_leaderboard(range_key)` | `GET /hq/analytics/leaderboard` | Per-studio composite scores + component rates |
| `get_studio_analytics(store_id, range_key)` | `GET /hq/analytics/studio/<store_id>` | Per-studio funnel, variance trend, and recent runs |

**Leaderboard score formula** (tunable constants at top of `analytics_begin_count.py`):
```
score = round(
    (completion_pct * SCORE_WEIGHT_COMPLETION +
     adjustment_pct * SCORE_WEIGHT_ADJUSTMENT +
     follow_through_pct * SCORE_WEIGHT_FOLLOW_THROUGH) * 100
)
```
Weights: Completion 0.40, Adjustment 0.35, Follow-Through 0.25.

**Range handling:** `_validated_range(req)` in `app.py` accepts `'4w'`, `'12w'`, `'all'`; defaults to `'4w'` for anything else.

**"Abandoned" query-time classification:** `status = 'abandoned'` OR (`status = 'in_progress'` AND `started_at < datetime('now', '-3 days')`). The DB column is never rewritten by analytics reads.

**Files touched:** `app.py` (4 new routes, deleted old /hq/analytics orphan route, removed `analytics_data` import, simplified `hq_section_analytics`), `analytics_begin_count.py` (new), `templates/fragments/studios.html` (removed `storeAnalytics` injection), `templates/hq_shell.html` (removed sparkline JS), `analytics_data.py` (deleted), `templates/analytics.html` (deleted)

#### Phase 2b — Frontend

**New file: `templates/fragments/analytics.html`** — complete 3-tab HQ Analytics UI.

Structure: `.hq-analytics-subnav` div (hoisted into sticky header by `loadSection()`) + `#analytics-content` div + a single IIFE `<script>`.

**IIFE-scoped state:**

| Variable | Description |
|---|---|
| `_tab` | Current active tab (`'overview'` / `'participation'` / `'leaderboard'`) |
| `_range` | Current range key (`'4w'` / `'12w'` / `'all'`); initialized to `'4w'` |
| `_cache` | Object keyed by `tab + ':' + range`; cleared entirely on range change |
| `_charts` | Object mapping canvas ID → Chart instance; destroyed before re-render |
| `_expandedStoreId` | Currently expanded leaderboard drill-down store ID (or null) |

**Public interface** (exported to `window` for `onclick=` attribute compatibility):

| Function | Trigger | Behavior |
|---|---|---|
| `_aTabSwitch(tab)` | Sub-tab link click | Switches tab, updates underline indicator, checks cache, fetches if miss |
| `_aRangeChange()` | Range dropdown `onchange` | Reads `sel.value`, updates `_range`, clears `_cache`, re-fetches current tab |
| `_aToggleDrill(storeId, trEl)` | Leaderboard row click | Expands/collapses per-studio drill-down row in-place |
| `_aPartSort(col)` | Participation table header click | Re-sorts participation rows client-side |
| `_aLbSort(col)` | Leaderboard table header click | Collapses open drill-down, re-sorts leaderboard rows client-side |

**`_whenChart(fn)` polling helper:** Polls `typeof Chart !== 'undefined'` every 50ms for up to 2 seconds; handles the CDN load / IIFE execution race condition.

**Files touched:** `templates/fragments/analytics.html` (complete rewrite)

#### Bug Fixes (post-Phase 2a, pre-Phase 2b)

**Bug 1 — Leaderboard scores always 0:**
- Root cause: `round()` was applied to the weighted sum (a float 0–1) before multiplying by 100. Any sum < 0.5 rounded to 0.
- Fix: moved `* 100` inside `round()` so the full 0–100 range is preserved.
- File: `analytics_begin_count.py`

**Bug 2 — Completed runs overwritten as abandoned:**
- Root cause: `mark_stock_check_abandoned()` ran an unconditional `UPDATE … SET status = 'abandoned'`. When a user clicked "Start a new Stock Check" on the Step 7 completion screen, the just-finished `completed` run was overwritten.
- Fix: added `AND status != 'completed'` to the `WHERE` clause. The function is now a no-op on completed rows.
- File: `app.py`

---

### Dashboard Retirement

**Summary:** The old HQ Dashboard (George's reconciliation dashboard — CSV-upload based, powered by `reconcile.py`) was retired. `reconcile.py` is NOT deleted — it continues to power the Studios section status dots, the header `UPDATED:` timestamp, and the `/hq/refresh` endpoint.

**What was deleted:**
- `templates/fragments/dashboard.html` — the entire dashboard fragment

**What was changed:**

| File | Change |
|---|---|
| `app.py` | `hq_section_dashboard()` now returns `redirect(url_for('hq_section_analytics'))` instead of calling `run_reconciliation()` + rendering the deleted fragment |
| `app.py` | `hq_index()` (`GET /hq/`) still calls `run_reconciliation()` to populate `data.last_loaded` for the shell header timestamp — unchanged |
| `templates/hq_shell.html` | Removed `DASHBOARD` tab `<a>` and its `|` pipe from the section nav; three tabs remain: ANALYTICS \| DATABASE \| STUDIOS |
| `templates/hq_shell.html` | Removed `initDashboard()`, `toggleDetail()`, `applyFilters()`, `showEmailDraft()`, `closeEmailModal()`, `copyEmailDraft()` functions (dashboard-only; 70+ lines removed) |
| `templates/hq_shell.html` | Removed two dashboard conditionals from `loadSection()` and `doRefresh()` (`if (section === 'dashboard') initDashboard()`, `if (currentSection === 'dashboard') loadSection('dashboard')`) |
| `templates/hq_shell.html` | Changed initial-load IIFE from `if (section) loadSection(section)` to `var section = params.get('section') \|\| 'analytics'; loadSection(section)` — Analytics is now the default landing section |
| `templates/macros.html` | Removed `DASHBOARD` link and its `|` pipe from the `section_nav()` macro (used by legacy `database.html`, `settings.html`, `upload.html`) |

**`reconcile.py` call sites — NOT dead code:**

| Call site | Still active | Purpose |
|---|---|---|
| `hq_index()` | ✅ | Populates `data.last_loaded` for the `UPDATED:` header timestamp |
| `hq_refresh()` | ✅ | Refreshes the timestamp on POST |
| `hq_section_studios()` | ✅ | Builds `recon_status` and `recon_data` for the status dots in the Studios table and profile panel |
| `hq_email_draft()` | ✅ | Still referenced by the email-draft route |
| `hq_section_dashboard()` | 🔴 dead | Removed with the old function body; now just `return redirect(...)` |

---

### Start Your Stock Check — Feature Flag

**What was built:** A boolean constant `SHOW_START_STOCK_CHECK` at the top of `app.py` controls whether the legacy "Start Your Stock Check" button is rendered on the Studio homepage.

- Constant: `SHOW_START_STOCK_CHECK` (line ~56 in `app.py`)
- When `False`: the button is hidden; studios see only BEGIN COUNT
- When `True`: the button is rendered (current value — re-enabled after initial hide)
- Passed to `GET /studio/` as `show_start_stock_check` template variable
- Template conditionally renders the button: `{% if show_start_stock_check %} … {% endif %}`
- Intent: allows HQ to suppress the legacy flow while Begin Count is validated in production, then re-enable with a one-line code change

**Files touched:** `app.py`, `templates/studio.html`

---

### Studio Homepage Welcome Message

**What was built:** A personalized welcome message displayed on the Studio homepage below the header.

**Content:** `"Hey, {neighborhood}. Below are your assigned SKUs for Week {N}. Hit 'Begin Count' to start."`

**`parse_neighborhood(store_name)` helper in `app.py`:** Extracts the neighborhood/location label from a full store name string. Returns the store name as-is if parsing finds no recognizable pattern (safe fallback).

**Week number:** `date.today().isocalendar()[1]` — the current ISO calendar week number (1–53). Computed at request time in `GET /studio/` and passed as `welcome_week_number`.

**Visual treatment:** Font size increased ~15–20% above base body size; `white-space: nowrap` and overflow handling so the greeting stays on one line; prominent placement above the SKU grid.

**Files touched:** `app.py`, `templates/studio.html`

---

### Damage-Adjustment Warning Interstitial (Begin Count)

**What was built:** A new screen inserted between the intro screen and Step 1 in the Begin Count flow. It is not a numbered step and does not trigger any DB writes or timer start.

**User flow:** Intro → Warning screen → (confirm) → Step 1 (DB row created, timer starts)

**Warning screen (`#step-warning`):**
- Heading: "Before You Begin"
- Amber warning box (`#fef3c7` background, `#d97706` border): *"! WARNING ! All unprocessed damages MUST be adjusted in Brightpearl prior to proceeding to the next step or your Stock Check counts will be inaccurate."*
- Lavender confirm button (`#e8b4f8`): full acknowledgment sentence — *"I confirm that I understand and have made all necessary damage adjustments in Brightpearl. I'm ready to continue my Weekly Stock Check."*
- Back link (gray, underlined): returns to intro without side effects

**Navigation functions added to `studio_tutorial.html`:**

| Function | Behavior |
|---|---|
| `goToWarning()` | Shows `#step-warning`; does NOT call `saveStep()`; `currentClientStep` stays 0; step indicator stays hidden |
| `confirmWarning()` | Calls `goToStep('step-1')` — this is when the DB row is created and the timer starts |
| `backToIntro()` | Shows `#step-intro`; calls `onCounterNameInput()` to re-evaluate button gate; no step-counter side effects |

**`#step-warning` is not in `STEP_ID_TO_NUM`**: the warning screen is invisible to the step indicator and the analytics persistence hooks.

**Files touched:** `templates/studio_tutorial.html`

---

### Step 3 — Print SKU List Button

**What was built:** A "Print SKU List" button added to the Step 3 SKU reference grid screen inside the Begin Count wizard.

**Implementation:** Scoped duplicates of the Studio main-page print logic (`handleStep3Print`, `executeStep3Print`) targeting `#step3-search` (search input) and `#step3-grid` (card grid) within Step 3. Avoids polluting the outer Studio page's `handlePrint`/`executePrint` functions.

**Behavior:** Mirrors the studio main page print flow:
- If no active search filter: calls `window.print()` immediately
- If a search filter is active: shows a modal with "PRINT ALL [X] SKUS" and "PRINT [X] MATCHING SKUS" options

**Step 3 body text** updated to reference the new button.

**Files touched:** `templates/studio_tutorial.html`

---

### Step 4 — Per-Department Editable Columns

**What was built:** The Step 4 variance table's single "Counted" input column was replaced with four per-department editable input columns, plus computed aggregate columns.

**New column structure:**

| Column | Type | Description |
|---|---|---|
| SKU | read-only | Uppercase SKU code |
| Product Name | read-only | Description from master |
| On-Hand | read-only | From Step 1 BP upload |
| Accessory | editable input | Department count |
| Bins & Backstock | editable input | Department count |
| DCR/Piercing Room | editable input | Department count |
| Visual Display | editable input | Department count |
| Total Counted | computed | Sum of 4 department inputs |
| Variance | computed | Total Counted − On-Hand |

**Session structure:** `begin_count_oc_counted` is now nested: `{sku: {"Accessory": int, "Bins & Backstock": int, "DCR/Piercing Room": int, "Visual Display": int}}`. Each department value is stored separately.

**DB storage:** Aggregate only — `stock_check_skus.counted = sum(dept_values)`. The per-department breakdown is session-only; not persisted to the DB.

**`map_department_desc()` helper in `app.py`:** Maps the four department description strings to their short display labels for the column headers.

**Backwards-compatible migration handler in `app.py`:** On session resume, if `begin_count_oc_counted` contains flat `{sku: int}` entries (old format), they are popped with a `stderr` log. This handles any in-flight sessions from before the schema change.

**Step 7 crosscheck:** Reads `session['begin_count_oc_counted']` using `sum(dept_dict.values())` if the value is a dict, otherwise reads the int directly (flat-shape fallback).

**Files touched:** `app.py`, `templates/studio_tutorial.html`

---

### Step 6 — Condensed Variance Summary

**What was built:** The Step 6 screen, previously an instructional-only advance screen, now shows a condensed read-only variance summary table.

**Table behavior:**
- Shows only SKUs with non-zero variance (Counted ≠ On-Hand)
- Sorted by absolute variance descending (largest discrepancies first)
- Computed from the Step 4 department cells via `_step4DescMap` — reads the same session data as the Step 4 inputs
- If all variances are zero, shows a "No variances detected." message instead of the table

**Stale-render fix:** `renderStep6VarianceTable()` is called inside `goToStep('step-6')` (in addition to `DOMContentLoaded`) so the table always reflects the latest Step 4 data, even if the user navigated back and changed counts after the initial page load.

**Step 6 body text** updated to describe the condensed table view.

**Files touched:** `templates/studio_tutorial.html`

---

### Top Sellers CSV Upload (HQ Database)

**What was built:** A new upload section in the HQ Database page for `Top_Sellers.csv` — the network-aggregated weekly top sellers data used by the SKU assignment algorithm.

**UI (in `templates/fragments/database.html`):**
- Positioned between "SKU Status File" and "SKU Prices File" sections
- Status line: `"Top_Sellers.csv — N SKUs — Last updated: YYYY-MM-DD HH:MM:SS"` or `"No file uploaded yet."` if absent
- Unknown-SKU warning block (amber: `#fffbeb` background, `#d97706` border): lists any SKUs in Top_Sellers.csv that are not in the master SKU file; those SKUs will be ignored by the assignment algorithm until added to the master. Capped at 20 visible SKUs with "…and N more" suffix.
- Upload form posts to `POST /hq/database/upload-top-sellers`

**Route: `POST /hq/database/upload-top-sellers`** (new)
- Accepts `top_sellers_file` (CSV, `.csv` extension required)
- Archives existing `Top_Sellers.csv` before overwrite (file_type `'top_sellers'`)
- Saves to `MASTER_DIR/Top_Sellers.csv`
- Flash message confirms count of SKUs loaded

**`load_top_sellers()` in `app.py`:**
- Reads `MASTER_DIR/Top_Sellers.csv`; returns `[]` if file absent (with `stderr` log on missing file)
- Expected columns: `sku`, `rank` (integer)
- Returns list of `(sku_uppercase, rank)` tuples sorted by rank ascending

**`GET /hq/section/database` additions:** passes `top_sellers_exists`, `top_sellers_count`, `top_sellers_last_updated`, and `unknown_top_seller_skus` to the fragment.

**Files touched:** `app.py`, `templates/fragments/database.html`

---

### SKU Assignment Automation Feature

**Summary:** New 4th HQ tab "SKU ASSIGNMENT" providing a fully algorithm-driven weekly SKU list recommendation, with HQ override editing, Save & Publish, and a full audit trail with drill-down history. Replaces the manual SKUList upload workflow for weekly list generation.

**Files touched:** `app.py`, `sku_assignment.py` (new module), `templates/hq_shell.html`, `templates/fragments/sku_assignment.html` (new fragment)

---

#### Algorithm (`sku_assignment.py`)

**New module.** No `from app import …` — lazy imports only, avoids circular import.

**Scoring formula:**

```
composite_score = (sales_score × 0.60) + (time_score × 0.40)
```

- `sales_score`: rank-based; derived from network-wide Top_Sellers ranking (rank 1 = 1.0, rank N = ~0.0; linear interpolation)
- `time_score`: weeks since last counted (capped at 12); `min(weeks, 12) / 12`
- Target list size: 20 (configurable constant `ASSIGNMENT_TARGET_LIST_SIZE`)
- When Top_Sellers.csv is absent: `sales_score = 0` for all SKUs; time_score drives ranking entirely
- Tiebreaker: alphabetical by SKU

**Eligibility rules (applied before scoring):**

| Rule | Effect |
|---|---|
| `status_map.get(sku) == 'active'` required | SKUs absent from SKU_Status.csv, or with any status other than `'active'`, are excluded (`inactive_excluded` counter) |
| `status_map.get(sku) == 'sunset'` | Excluded and counted separately (`sunset_excluded` counter) |
| `first_seen_at > today − 28 days` | New SKUs excluded for 4 weeks after first appearing in master (`new_sku_delayed` counter) |

**`sku_first_seen` table:** Tracks when each SKU first appeared in the master. Bootstrap logic: on first run (empty table), all existing SKUs get `first_seen_at = now − 365 days` so they are immediately eligible. Migration guard: if >100 rows were all inserted within 24 hours (bulk bootstrap detected), bulk-updates them to `now − 365 days`. Ongoing: `INSERT OR IGNORE` uses `CURRENT_TIMESTAMP` for genuinely new SKUs.

**`generate_assignment(week_id)` return shape:**

```json
{
  "week_identifier": "MM-DD-YY",
  "selected": [
    {
      "sku": "PS001ABC",
      "description": "...",
      "rank": 3,
      "sales_score": 0.92,
      "weeks_since_counted": 4,
      "time_score": 0.33,
      "composite": 0.686,
      "reasoning": "Top seller (rank 3) + last counted 4 weeks ago"
    }
  ],
  "stats": {
    "eligible_pool_size": 287,
    "sunset_excluded": 60,
    "inactive_excluded": 800,
    "new_sku_delayed": 3,
    "total_master_skus": 1146
  },
  "top_sellers_missing": false
}
```

**Reasoning strings** cover all combinations of: top seller vs. non-top-seller × never counted / counted this week / N weeks ago / 12+ weeks ago × top_sellers_missing flag. The `was_actually_counted = last_dt is not None` flag ensures "never counted" and "counted this week" are never conflated.

---

#### Database Schema Additions

Two new tables added to `store_profiles.db` via `init_store_db()`:

**`sku_first_seen`:**

| Column | Type | Notes |
|---|---|---|
| `sku` | TEXT PRIMARY KEY | Uppercase |
| `first_seen_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**`sku_assignment_runs`:**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `triggered_at` | TIMESTAMP | |
| `triggered_by_username` | TEXT | HQ session username |
| `target_week_identifier` | TEXT | `MM-DD-YY` |
| `selected_skus_json` | TEXT | JSON array of full detail objects (rank, scores, reasoning) |
| `selected_skus_count` | INTEGER | |
| `published` | BOOLEAN | DEFAULT 0 |
| `published_at` | TIMESTAMP | |
| `published_filename` | TEXT | Written SKUList filename |
| `weight_sales` | REAL | Algorithm weight used |
| `weight_time` | REAL | Algorithm weight used |
| `new_sku_delay_weeks` | INTEGER | |
| `target_list_size` | INTEGER | |
| `notes` | TEXT | |
| `had_overrides` | BOOLEAN | DEFAULT 0; added via idempotent `ALTER TABLE` |
| `overrides_json` | TEXT | JSON with `added`, `removed`, `algorithm_original_skus`; added via idempotent `ALTER TABLE` |

**Index:** `CREATE INDEX IF NOT EXISTS idx_stock_check_skus_sku ON stock_check_skus(sku)` — added for time-since-counted lookups.

---

#### API Endpoints

| Route | Method | Description |
|---|---|---|
| `GET /hq/section/sku-assignment` | GET | Renders the SKU assignment fragment |
| `GET /hq/sku-assignment/preview` | GET | Read-only; calls `generate_assignment()`; returns algorithm result JSON |
| `POST /hq/sku-assignment/publish` | POST | Writes SKUList file, inserts audit row. Accepts optional `{"skus": [...]}` body for HQ override list |
| `GET /hq/sku-assignment/runs` | GET | Publish history; supports `?month=YYYY-MM` and `?sku=SUBSTRING` filters; no row cap |
| `GET /hq/sku-assignment/runs/months` | GET | Returns distinct `YYYY-MM` strings for the month filter dropdown |
| `GET /hq/sku-assignment/searchable-skus` | GET | Returns all eligible `{sku, description}` entries for the override autocomplete |

**Publish behavior details:**
- If no `skus` key in body: publishes the algorithm's output exactly
- If `skus` key present: validates each against master SKU list and `status='active'`; returns HTTP 400 with error if any are invalid
- Diff computed against algorithm's output: `added_skus` (in client list, not in algo), `removed_skus` (in algo, not in client)
- `had_overrides = True` if either list is non-empty
- `overrides_json` stores `{added: [...], removed: [...], algorithm_original_skus: [...]}`
- `selected_skus_json` stores full detail objects for drill-down (not just SKU strings)
- Written file: `SKU_LIST_MM.DD.YY.csv` in `/input/`

---

#### HQ Shell Integration

**4th nav tab added to `templates/hq_shell.html`:**
```html
<span class="hq-pipe">|</span>
<a href="#" class="hq-section-link" data-section="sku-assignment" ...>SKU ASSIGNMENT</a>
```
Section nav now reads: ANALYTICS | DATABASE | STUDIOS | SKU ASSIGNMENT

---

#### HQ SKU Assignment UI (`templates/fragments/sku_assignment.html`)

**Structure:** `.hq-analytics-subnav` (hoisted into sticky header by `loadSection()`) + `#sku-assignment-content` + single IIFE `<script>`.

**State variables (IIFE-scoped):**

| Variable | Description |
|---|---|
| `_preview` | Raw algorithm result from `/preview` |
| `_runs` | Publish history rows from `/runs` |
| `_eligibleSkus` | `[{sku, description}]` array from `/searchable-skus`; loaded once for autocomplete |
| `_editedList` | Current in-memory SKU list (mutable; user edits apply here) |
| `_originalList` | Algorithm's output list (immutable reference for diff display) |
| `_publishBanner` | Success/error message string |
| `_expandedRunId` | ID of the currently expanded drill-down row (or null) |
| `_histMonths` | List of distinct YYYY-MM strings for the month filter dropdown |
| `_histFilterMonth` | Currently selected month filter value |
| `_histFilterSku` | Current SKU substring search string |

**Preview section — stat boxes:**

| Box | Shows |
|---|---|
| SELECTED | Count of SKUs in `_editedList`; "EDITED" chip appears if list differs from algorithm output |
| ELIGIBLE | `stats.eligible_pool_size` |
| SUNSET EXCLUDED | `stats.sunset_excluded` (hidden if 0) |
| NOT ACTIVE EXCLUDED | `stats.inactive_excluded` (hidden if 0) |
| NEW SKU DELAY | `stats.new_sku_delayed` (hidden if 0) |

**Editable preview list:**
- Each SKU row shows: rank, SKU, description, sales score, time score, composite, reasoning
- × button on each row calls `_skuRemove(sku)` — removes from `_editedList`, triggers `_render()`
- Empty list disables the Save & Publish button

**"+ Add SKU" override input:**
- Text input at the bottom of the preview table
- `oninput` calls `_skuAddFilter()` — client-side filters `_eligibleSkus` (excluding already-listed SKUs), shows dropdown of up to 10 matches
- Clicking a dropdown item calls `_skuAddSelect(sku, description)` — appends to `_editedList` with `reasoning: "Added by HQ override"`, triggers `_render()`
- Blur with 180ms delay allows `mousedown` on dropdown items before hiding

**Save & Publish button:**
- Label: `"SAVE & PUBLISH (N SKUs)"` where N is current `_editedList.length`
- Disabled when `_editedList` is empty
- Confirm dialog text is context-aware:
  - No overrides: standard confirmation
  - With overrides: includes `"You've added X SKUs and removed Y SKUs from the algorithm's recommendation."`
- On confirm: `POST /hq/sku-assignment/publish` with `{skus: [...]}` body only if list differs from algorithm output
- On success: sets `_publishBanner`, reloads history via `_histFetch()`

**Publish History:**
- Month filter dropdown (populated from `/runs/months`; default "All months")
- SKU substring search input (300ms debounce)
- Filters are AND-combined; changing either re-fetches from `/runs?month=...&sku=...`
- Table columns: Week of | Triggered | By | SKUs | File | Status | Edited (✎ chip if `had_overrides`)
- Clicking a row expands inline drill-down (clicking again collapses)

**Drill-down (`_renderDrill(row)`):**
- 4 algorithm context boxes: Sales Weight | Time Weight | Target List Size | New SKU Delay
- "HQ Override Applied" callout (lavender tint `#f8f0ff`, left border `#e8b4f8`) — only shown if `had_overrides=true`:
  - Lists added SKUs (with descriptions)
  - Lists removed SKUs (with descriptions)
- Full per-SKU table from that run (rank, description, scores, reasoning); SKU text highlighted if `_histFilterSku` is active
- Table data sourced from `selected_skus_json` (full detail objects); gracefully handles old rows that stored plain SKU strings

**Styling:** Matches HQ Analytics visual language — `hq-table`, `hq-btn hq-btn-lavender`, `hq-section`, stat box styling, `hq-subsection-heading`.

---

### Known Issues

#### KI-1: HQ Analytics range selector resets on sub-tab switch

**Symptom:** When the user changes the range dropdown on any Analytics sub-tab (e.g., to "Last 12 weeks" or "All time") and then clicks a different sub-tab link (OVERVIEW / PARTICIPATION / LEADERBOARD), the dropdown visually reverts to "Last 4 weeks."

**Impact:** Cosmetically confusing. Functionally a non-issue with the current test dataset — all test runs occurred within the first 4 weeks of data, so the backend returns identical results for all three range values. Will become functionally impactful once data spans more than 4 weeks.

**Root cause:** Diagnosed twice by static code analysis during the session; both passes concluded that the `_aTabSwitch` code path does not touch the range selector and should not reset it, which contradicts the live observed behavior. The cause was not pinpointed from code reading alone.

**Hypothesis (unverified):** The `.hq-analytics-subnav` DOM node (which contains the range select) is being silently re-attached or re-parsed during a tab-switch sequence, causing the select element to lose its transient `.value` state and revert to its default first-option value.

**Suggested investigation:** Add a `MutationObserver` on `#hq-header-subnav` plus `console.log` instrumentation in `_aTabSwitch` to trace exactly what DOM mutations occur between the range change and the next sub-tab click. Code-reading alone has not been sufficient to locate the root cause.

**Files involved:** `templates/fragments/analytics.html` (JS IIFE), `templates/hq_shell.html` (`loadSection()` hoist logic)

**Resolution:** Deferred.

---

#### KI-2: SKU Assignment Publish History "By" column shows "unknown"

**Symptom:** The "By" column in the SKU Assignment publish history table shows "unknown" for every publish run, regardless of which HQ user triggered the publish.

**Root cause:** The `POST /hq/sku-assignment/publish` endpoint is not reading `session.get('display_name')` (or the equivalent HQ username key) when inserting the `sku_assignment_runs` row. The `triggered_by_username` column is written as `None` / empty.

**Impact:** Cosmetic only. The run data, SKU list, and override metadata are all stored correctly; only the attribution column is blank.

**Files involved:** `app.py` (`hq_sku_assignment_publish()`)

**Resolution:** Deferred.
