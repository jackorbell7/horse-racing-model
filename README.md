# Horse Racing Model — Streamlit App

## Setup Instructions

### Step 1 — Upload to GitHub

1. Go to **github.com** and sign in
2. Click the **+** button top right → **New repository**
3. Name it `horse-racing-model`
4. Keep it **Private**
5. Click **Create repository**
6. Click **uploading an existing file**
7. Upload both files: `app.py` and `requirements.txt`
8. Click **Commit changes**

### Step 2 — Deploy on Streamlit

1. Go to **share.streamlit.io** and sign in with GitHub
2. Click **New app**
3. Select your `horse-racing-model` repository
4. Main file path: `app.py`
5. Click **Deploy**

Your app will be live in about 2 minutes at a URL like:
`https://yourusername-horse-racing-model-app-xxxxx.streamlit.app`

---

## How to Use

### Race Entry tab
1. Fill in **Race Setup** — date, course, distance, surface, ground, class
2. Set number of horses
3. For each horse:
   - Type the **name**, **OR rating**, **today's odds**, **stall**
   - Paste the **Racing Post string** (e.g. `18Oct25 Cat 7 Gd 4Hc 6K`)
   - Paste the **position string** (e.g. `5/10  (3½L Mudamer 9-11) 11/2`)
   - Type **TS** and **RPR** (or leave blank if dash)
   - Repeat for Race 2 and Race 3
4. Click **Run Model**
5. Model outputs rank, probability, edge, and bet recommendation

### After the race
- Enter the winner, 2nd, 3rd
- Select outcome
- Click **Save to Results Log**

### Results Log tab
- See all logged races
- Download as CSV to send for analysis

---

## RP String Format
`18Oct25 Cat 7 Gd 4Hc 6K`
- `18Oct25` = date
- `Cat` = course code (Cat = Catterick → Turf)
- `7` = distance (furlongs if no m prefix)
- `Gd` = going
- `4Hc` = race type/class
- `6K` = prize money

## Position String Format
`5/10  (3½L Mudamer 9-11) 11/2`
- `5/10` = finished 5th of 10
- `3½L` = beaten 3.5 lengths
- `Mudamer 9-11` = winner and their weight
- `11/2` = SP
