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

## HQ Dashboard (`/hq/?section=dashboard`)

### SPA Shell (applies to all HQ sections)
- [ ] Header displays STUDS logo with "(CONFIDENTIAL)" label
- [ ] Left nav box (lime): HQ (current/bold) | STUDIO | LOGOUT
- [ ] Right nav box (lavender): FILES | REFRESH | SETTINGS
- [ ] User display name shown below header (if logged in as named user)
- [ ] "UPDATED:" timestamp shown below header, updates on refresh
- [ ] Section nav bar: DASHBOARD | ANALYTICS | DATABASE | STUDIOS
- [ ] Clicking a section link loads its content via AJAX into the main area without full page reload
- [ ] Active section link is visually highlighted
- [ ] Browser back/forward buttons navigate between sections via history.pushState
- [ ] Direct URL access with `?section=` parameter loads the correct section on page load
- [ ] Page scrolls to top when switching sections

### Summary Bar
- [ ] Displays Total Studios count
- [ ] Displays Updated count (green)
- [ ] Displays Discrepancy count (red)
- [ ] Displays Incomplete count (gray)
- [ ] Displays current SKU list filename (or dash if none)
- [ ] Displays SKU count from the loaded list (or dash if none)
- [ ] Displays audit trail date range as "min -> max" (or dash if no audit trail)

### Bypass Banner
- [ ] If no SKU list file is present, a warning banner appears: "No SKU list loaded -- reconciling all variance SKUs..."
- [ ] In bypass mode, all variance SKUs are treated as active (no intersection filter)

### Warnings
- [ ] Warnings are displayed in a yellow/orange banner area below the summary bar
- [ ] Warning if multiple SKU lists found (uses most recent by date in filename)
- [ ] Warning if multiple audit trails found (uses most recent by date in filename)
- [ ] Warning if a variance file fails to parse

### Filter & Sort Controls
- [ ] Filter dropdown: All / Updated / Discrepancy Detected / Incomplete
- [ ] Selecting a filter hides non-matching store rows
- [ ] Incomplete filter matches both "Incomplete (missing file)" and "Incomplete (unrecognized file format)"
- [ ] Sort dropdown: Store ID / Status / Discrepancy Count
- [ ] Store ID sorts numerically ascending
- [ ] Status sorts: Discrepancy Detected first, then Incomplete, then Updated
- [ ] Discrepancy Count sorts descending (highest first)

### Action Links
- [ ] EXPORT CSV link downloads a CSV file of all reconciliation data
- [ ] ARCHIVE link navigates to the archive browser page

### Store Table
- [ ] One row per store (all seeded stores always shown — 41 real studios in sandbox; count grows as studios are added — plus any extra variance files)
- [ ] Columns: expand arrow | Studio name | Status badge | Assigned SKUs | Discrepancies | Net Discrepancy
- [ ] Status badge colors: Updated (green), Discrepancy Detected (red), Incomplete (gray)
- [ ] Stores with no variance file show "Incomplete (missing file)"
- [ ] Stores with unrecognized variance file schema show "Incomplete (unrecognized file format)"
- [ ] Clicking a store row or its arrow expands/collapses the detail row
- [ ] Expand arrow rotates from right-pointing to down-pointing when expanded
- [ ] Column headers are clickable to sort: Studio (string), Status (string), Assigned SKUs (number), Discrepancies (number), Net Discrepancy (number)
- [ ] Sort indicator arrow (up/down) appears on the active sort column
- [ ] Clicking the same column header toggles between ascending and descending

### Store Detail Row (Expanded)
- [ ] Shows a sub-table of SKU-level details
- [ ] Detail columns: SKU | Product ID | Required Push | Location | Item Cost Price | Actual Push | Discrepancy
- [ ] Non-zero discrepancy values are visually highlighted
- [ ] If status is "Discrepancy Detected", a GENERATE EMAIL button appears
- [ ] If status is "Updated" with no discrepancies, shows "No discrepancies -- all SKUs matched."

### Email Draft Modal
- [ ] Clicking GENERATE EMAIL fetches draft from `/hq/email-draft/<store_id>` via AJAX
- [ ] Modal displays: title "Email Draft -- [Store Name]", To field (editable), Subject field (readonly), Body field (readonly textarea)
- [ ] To field is pre-populated with the store email from settings (if configured)
- [ ] Subject format: "[Store Name] -- Stock Check Discrepancy"
- [ ] Body includes greeting, discrepancy explanation, SKU-by-SKU list, and sign-off
- [ ] Each SKU line shows: SKU, Required Adjustment, Actual Adjustment, Discrepancy
- [ ] COPY TO CLIPBOARD button copies "To: ... Subject: ... Body: ..." to clipboard
- [ ] After copying, button text changes to "Copied!" for 2 seconds then reverts
- [ ] Close button (X) closes the modal
- [ ] Clicking outside the modal content closes it

### Refresh
- [ ] REFRESH button in header sends POST to `/hq/refresh`
- [ ] On success, updates the "UPDATED:" timestamp in the header
- [ ] If currently on dashboard section, reloads the dashboard content
- [ ] On failure, shows an alert with the error

### Export CSV (`/hq/export`)
- [ ] Downloads a CSV file named `STUDS_Dashboard_Export_YYYYMMDD_HHMMSS.csv`
- [ ] CSV columns: Store ID, Store Name, Status, SKU, Product ID, Required Push, Location, Item Cost Price, Actual Push, Discrepancy
- [ ] Includes all SKU detail rows for stores that have variance data
- [ ] Stores without data get a single row with empty SKU fields

---

## HQ Analytics (`/hq/?section=analytics`)

### Sub-Navigation
- [ ] Sticky sub-nav bar with links: OVERVIEW | COMPLIANCE TREND | STORE RANKINGS | DISCREPANCY SKUS | DISTRIBUTION | STORE GROUPS
- [ ] Sub-nav becomes fixed to top of viewport when scrolled past its natural position (JS-based sticky since CSS sticky doesn't work in SPA content div)
- [ ] Clicking a sub-nav link smooth-scrolls to the corresponding panel
- [ ] Scroll offset accounts for the fixed header height and sub-nav height

### Network Summary Panel (OVERVIEW)
- [ ] Displays Network Compliance rate as a percentage
- [ ] Displays Average Update Lag in hours
- [ ] Displays Total Discrepancy Units
- [ ] Displays Chronic Offenders count (compliance < 60%) in red, clickable to scroll to Store Groups
- [ ] Displays Top Performers count (compliance >= 90%) in green, clickable to scroll to Store Groups

### 12-Week Compliance Trend (COMPLIANCE TREND)
- [ ] Stacked bar chart (Chart.js)
- [ ] X-axis: 12 week labels
- [ ] Y-axis: count, max 40
- [ ] Three datasets: Updated (lime), Discrepancy (red), Incomplete (gray)
- [ ] No animation
- [ ] Legend at bottom

### Studio Compliance Leaderboard (STORE RANKINGS)
- [ ] Sortable table with columns: Rank | Studio | Compliance Rate | Avg Lag | Discrepancy Units | Trend
- [ ] Top 5 rows visually highlighted (green/top style)
- [ ] Bottom 5 rows visually highlighted (red/bottom style)
- [ ] Trend column shows: up arrow + "Improving" (green), down arrow + "Declining" (red), right arrow + "Stable" (gray)
- [ ] All columns except Trend are sortable by clicking headers

### Chronic Discrepancy SKUs (DISCREPANCY SKUS)
- [ ] Sortable table with columns: SKU | Description | Total Units | Studios Affected | Weeks Appearing
- [ ] All columns are sortable by clicking headers

### Discrepancy Size Distribution (DISTRIBUTION)
- [ ] Bar chart (Chart.js)
- [ ] X-axis: discrepancy size buckets
- [ ] Y-axis: store-weeks count
- [ ] Lavender bar color
- [ ] No legend

### Studio Groups (STORE GROUPS)
- [ ] Two-column layout side by side
- [ ] Left: Chronic Offenders (compliance < 60%) with red heading
- [ ] Right: Top Performers (compliance >= 90%) with green heading
- [ ] Each group shows a table: Studio | Compliance Rate | Trend (arrow only)

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

### Studio Analytics (within profile)
- [ ] Compliance Rate percentage
- [ ] Average Update Lag in hours
- [ ] Total Discrepancy Units
- [ ] 12-week sparkline bar chart: lime bars for 0 discrepancies, red bars for >0
- [ ] Frequently Discrepant SKUs table (if any): SKU | Description | Occurrences
- [ ] "No analytics data available." shown if no data exists

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
- [ ] Section nav links (DASHBOARD, ANALYTICS, DATABASE, STUDIOS) navigate to the SPA

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
- [ ] "Start a new Stock Check" secondary button triggers browser confirm dialog then POST /studio/tutorial/reset, which clears all `begin_count_*` session keys and redirects to `/studio/tutorial`

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

> Changes made in the active development session. All items below are scoped to the Begin Count flow (`/studio/tutorial`). The Start Your Stock Check flow (`/studio/stock-check/*`, `templates/stock_check.html`, `stock_check_count.html`, `stock_check_verify.html`) and its session keys (`bp_onhand`, `sc_counts`, `post_bp_onhand`, etc.) were not touched in any phase of this work.

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
| `POST /studio/tutorial/reset` | POST | Clears all 13 `begin_count_*` session keys; redirects to `/studio/tutorial` |

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
- Clears all 13 `begin_count_*` session keys
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
