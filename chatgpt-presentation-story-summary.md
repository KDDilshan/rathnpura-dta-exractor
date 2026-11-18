# ChatGPT – Presentation Story Summary

Source: https://chatgpt.com/share/6afcfc07-afd0-83e8-aecc-9cd6647bb155

---

## 🧑 User

Here's your full speech. It takes about **8.5 minutes** at a calm pace, so you finish before the 10-minute bell.

---

## 🟦 Slide 1: Title *(0:00 – 0:25)*

Good morning everyone. My name is Kavindu Dilshan, and I am from NSBM Green University. My co-author is my supervisor, Ms. Hirushi Dilpriya.



Our paper is about land price prediction in Colombo District. It asks one simple question: when a land price model looks very accurate, is it really learning about the land, or is it only remembering the place?

---

## 🟦 Slide 2: Problem *(0:25 – 1:25)*

We started with two gaps.



The first gap is about hazard. Land price models in Sri Lanka use market and amenity features, like land size and distance to roads. But they do not use flood or hazard data. This is strange, because Colombo floods often. For example, the Kelani Ganga flooded in June 2021 and October 2024, and Cyclone Ditwah hit in 2025.



The second gap is the more important one. Every study we reviewed tests its model with a random train–test split. This means listings from the same GN division are in both training and testing. So the model can simply remember the price level of that division.



So our key question is: how accurate is a land price model for a GN division it has never seen? This is the real situation when someone needs a price for a new area.

---

## 🟦 Slide 3: Objectives *(1:25 – 2:05)*

We had three objectives.



First, add satellite flood-hazard and terrain variables to a Colombo land price model, at GN-division level.



Second, measure accuracy on seen and unseen divisions. We keep the model, the features and the pipeline fixed. We change only the validation design.



Third, explain the gap, and test what really helps on unseen divisions: hazard variables, or the prices of nearby divisions.

---

## 🟦 Slide 4: Data *(2:05 – 2:55)*

Our data has 7,034 land listings from Ikman.lk, collected with academic permission. They cover 194 GN divisions in Colombo District.



The model has 49 features, and it predicts the log price per perch.



We started with 11 hazard and terrain variables. We screened them with fixed rules, decided before we looked at prices, and kept six. These are elevation, surface-water occurrence, height above drainage, distance to the nearest stream, distance to the Kelani Ganga, and Sentinel-1 radar flood maps from three flood events.



One important point: the listings do not give exact plot locations. So every listing in a division gets the same centre point. We have seven thousand rows, but only 194 different locations.

---

## 🟦 Slide 5: Method *(2:55 – 4:00)*

Here is our method. We scraped the listings, matched each one to a GN division, took hazard values in a one-kilometre buffer, and trained a tuned Random Forest.



All price trimming and target encoding is done inside each training fold, so no test information leaks into training.



Then we tested the same model in two ways.



On the left, A is a random 80/20 split, repeated with five seeds. The same division is in both training and testing, so the model can remember it.



On the right, B is a grouped split. The whole division is kept out of training. This is like predicting a completely new area. For B, we used GroupKFold with five folds, and we repeated it with 25 random grouped partitions to see how much the result changes.

---

## 🟦 Slide 6: Result 1 *(4:00 – 5:05)*

This is our main result.



On seen divisions, the R-squared is 78.97 percent. On unseen divisions, it falls to 27.90 percent. That is a drop of 51 percentage points.



Nothing changed except the validation design. Same model, same features, same pipeline.



The lighter bars show the original global pipeline. The gap is still there: 87.72 versus 30.28 percent. So the gap is not caused by preprocessing.



Also, the unseen result is unstable. The central 95 percent of partitions fall between 15.9 and 38.2 percent. So accuracy for a new area depends a lot on which areas you test.

---

## 🟦 Slide 7: Result 2 *(5:05 – 6:15)*

So why does this happen?



One feature, the target-encoded division name, carries 75.40 percent of the Gini importance. This feature is simply the average price of that division in the training data.



On a random split, it is the number one feature in permutation importance. On unseen divisions, it falls to number 34 out of 49, and removing it changes R-squared by zero.



Here is a simple example. Imagine the model has seen Kollupitiya, so it knows Kollupitiya is expensive. But if Bambalapitiya is new, the encoder has no value for it. So it gets the overall average, the same as every other new division. Then this feature tells the model nothing.



So the model learned to name the place, not to describe it. We call this the location-identity problem.

---

## 🟦 Slide 8: Result 3 *(6:15 – 7:30)*

So what helps on new divisions?



First, hazard variables. When we remove all six, accuracy changes by only minus 0.37 points. The 95 percent interval is minus 0.74 to minus 0.01. This does not pass the decision rule we set in advance. So the hazard effect is small and not robust.



Second, neighbour price. This is the inverse-distance-weighted average price of the five nearest training divisions. So for a new division, we use the prices of the areas around it.



Neighbour price alone reaches 45.57 percent. That is 17.67 points better than the Random Forest, and it is better in all 25 partitions.



If we add neighbour price to the forest but keep the identity feature, it improves only a little, to 29.73 percent. But when we remove the identity feature, the forest rises to 41.98 percent.



So describing a location works better than naming it.

---

> 🔔 **First bell (8 min):** you should be **starting slide 9** around here. If you're behind, speed up a little on slide 9.

---

## 🟦 Slide 9: Conclusion *(7:30 – 8:20)*

To conclude.



First, random-split accuracy for this kind of model mostly measures memory of known places: 79 percent on seen divisions, against 28 percent on unseen divisions.



Second, valuation studies should report both seen-division and unseen-division accuracy.



Third, satellite flood-hazard variables add very little in Colombo today.



And fourth, neighbour prices are the best location information for new areas.



For future work, we plan to use SAR coherence for better flood detection in built-up areas, plot-level geocoding so that point models like kriging can be used, and real data from high-hazard districts like Ratnapura, ideally with transacted prices.



Our main message is simple: **describe a location, don't just name it.**

---

## 🟦 Slide 10: Thank you *(8:20 – 8:30)*

Thank you very much for listening. I am happy to take your questions.

---

## 💡 Tips for tomorrow

- **Speak slowly.** You have extra time, so you don't need to rush.
- **Pause** for 2 seconds after "51 percentage points" and after the main message. Those are your strongest lines.
- **Look at the panel** and only glance at the slides.
- **Practise out loud 2–3 times today** with a phone timer.
- If you forget a line, look at the slide and **say the big number on it**. That's enough to keep going.

Want this as a printable file for your phone or to print? this is speecg given to me clude code and its hard to rember I found your session.\
\
📍 Your session\
Session: Track 1, Session 5: Energy, Environmental and Built-Environment Analytics\
Room: 008\
Time: 11:15 a.m. – 12:45 p.m.\
Mode: In person ✅\
Session chair: Dr. (Mrs.) Thilini Piyatilake\
Session coordinators: Mr. Madusanka Mithrananda, Mr. Supun Gajendrasinghe\
🔢 Your turn\
\
You are 5th of 7 presentations:\
\
53, hydropower forecasting\
64, ceiling material estimation\
128, smart waste collection\
146, solar net-load forecasting\
170, your paper\
172, electricity load forecasting\
175, PM2.5 forecasting\
\
Each talk is about 12 minutes, so your turn will probably be around 12:00 noon. The book says to ask the session coordinator for exact times.\
\
⏰ Tomorrow’s plan\
8:30 a.m.: registration opens. Coming at this time is best, so you can also see the opening ceremony.\
9:00 – 10:30: opening ceremony in the auditorium. It’s optional but good to attend.\
10:15 a.m. at the latest: arrive (1 hour before your session, as the email asked).\
\~11:00: go to Room 008, introduce yourself to the session chair and coordinators, and give them your USB.\
12:45: lunch.\
\
Good sign: your session is all about environment and forecasting. The panel will be interested in data and maps, so the flood and GN-division parts fit well.\
\
Want to go through practice questions for tomorrow?\
\
Dear Authors,\
Thank you for registering to present at ICACT 2026 on Wednesday, 18 November 2026. We look forward to welcoming you, whether you are presenting in person or online.\
Please find the attached ICACT 2026 Program Book for Authors. Use your CMT Paper ID to locate your assigned technical session. The handbook lists your track, session time and venue, session chair and co-chairs, and session coordinators.\
1\. Presentation slides\
If you received a separate email about slides that could not be located in the Supplementary Files section of Microsoft CMT, please follow the submission instructions in that email.\
2\. Presentation timing and Q&A\
Each presenter has 10 minutes to present, followed by 3–5 minutes of questions from the session panel. The timekeeper will use the following bell signals.\
\
8 minutes — one bell. You have two minutes remaining.\
10 minutes — two bells. Your presentation time is over. Please conclude and hand over to the session chair.\
11 minutes — three bells. If you are still presenting, please stop immediately.\
Online presenters\
If our online presentation team has already contacted you, please follow the instructions they provided. If you are still waiting to hear from them, the team will contact you today with joining instructions and guidance on presenting online. \
In-person presenters attending the main conference\
Please arrive at the NSBM Green University Auditorium by 8:30 a.m. for registration. The main programme begins at 9:00 a.m. On arrival, follow the registration team’s instructions for QR check-in, have your photograph taken at the conference backdrop, and complete registration before entering the Auditorium.\
The dress code for the main programme is formal office attire. Gentlemen should wear office trousers, a shirt of any colour, a tie, and a suit jacket. Ladies are welcome to wear formal office attire of their choice. A saree is optional.\
In-person presenters attending only their technical session\
Please arrive at the Faculty of Computing one hour before your allocated session begins. Complete registration and have your photograph taken at the designated area before proceeding to your session venue. Your session coordinators will contact you to confirm whether you plan to attend the main programme as well as your technical session. Please have your attendance plans ready when they get in touch.\
If you have any questions, please call me on [+94 77 457 1555]\(tel:+94%2077%20457%201555). I’ll be happy to help.\
Thank you for preparing for your session and for sharing your research at ICACT 2026. We look forward to your presentation.\
Thank you & Best Regards,\
\
Yasanthika Mathotaarachchi\
Lecturer Probationary\
Department of Software Engineering & Computer Security\
Faculty of Computing\
NSBM Green University\
Mahenwaththa, Pitipana, Homagama, Sri Lanka (→ www\.google.com). \
\
Mobile: [+94 (77) 457 1555]\(tel:+94%2077%20457%201555) | Email: [yasanthika.m@nsbm.ac.lk]\(mailto:yasanthika.m@nsbm.ac.lk) | Web: www\.nsbm.ac.lk \
Find us on: Facebook (→ www\.facebook.com) | YouTube (→ www\.youtube.com) | LinkedIn (→ www\.linkedin.com) | Instagram (→ www\.instagram.com) | Twitter (→ twitter.com)\
\
Disclaimer: This e-mail including any attachments therein is intended only for the exclusive use of the individual to whom it is addressed. The information contained hereinafter may be proprietary to National School of Business Management Ltd, confidential, privileged and exempt from disclosure under applicable law. If the reader of this e-mail is not the intended recipient, the reader is hereby put on notice that any use, dissemination, distribution or copying of this communication is strictly prohibited. If the reader has received this communication in error, kindly notify the sender by telephone or e-mail immediately and delete all copies of this e-mail and any attachments\
\
Important: the timing changed.\
\
⏱️ New timing\
Before: 7 minutes to talk + 5 minutes Q&A\
Now: 10 minutes to talk + 3–5 minutes Q&A\
Bell	Time	Meaning\
🔔 1	8 min	2 minutes left\
🔔🔔 2	10 min	Time’s up, finish\
🔔🔔🔔 3	11 min	Stop now\
\
What this means for you:\
\
Your notes take about 7 minutes. That’s fine, you don’t need to change any slides.\
You now have extra time, so speak slowly and calmly.\
Aim for 8–9 minutes. Try to be on slide 9 (Conclusion) at the first bell (8 min).\
You can use the extra time for the land example you understood well (Kollupitiya → Bambalapitiya). Say it on slide 7: “For example, if the model knows Kollupitiya but Bambalapitiya is new, it has no price for that name and just gives the average.”\
📂 Slides\
The email says that if your slides were missing from CMT, you’d get a separate email.\
If you didn’t get that email, your slides are fine ✅\
👔 Decide: main programme or only your session?\
\
Your session coordinators will call you to ask. Have your answer ready.\
\
Option A: main programme + your session\
\
Arrive at the NSBM Auditorium by 8:30 a.m.\
Wear formal dress: office trousers, a shirt, a tie and a suit jacket.\
\
Option B: only your session (11:15)\
\
Arrive at the Faculty of Computing by 10:15 a.m.\
Register and take the photo, then go to Room 008.\
\
I’d pick Option A. Your paper will be in the proceedings launch at the opening, and it’s good for networking.\
\
If you have any problems, call +94 77 457 1555 (Ms. Yasanthika).\
\
ok give me now the presntion speech for tommorrow\
\
Here’s your full speech. It takes about 8.5 minutes at a calm pace, so you finish before the 10-minute bell. thase areaddionla thisngs to uyr undertnading

---

## 🤖 ChatGPT

I understand now. I've reviewed your actual **10-slide presentation PDF (Paper ID 170)** and the speech you received from Claude Code.

First, congratulations! Tomorrow, 18 November, you're presenting your research at ICACT 2026.

I think the biggest problem isn't your research or the speech. It's that the speech is written like an essay. Trying to memorise 8–9 minutes of paragraphs is difficult, especially when you're standing in front of a panel.

**I recommend that you don't memorise the full speech.** Instead, learn the story of your research, slide by slide.

## Your presentation story in 9 steps

<box border radius="lg" gap={3} padding={3}>
  <row align="center" gap={2}>
    <badge color="info">1</badge>
    **The problem**
  </row>
  Sri Lankan land price models don't consider flood hazards, and random testing can make accuracy look misleadingly high.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="info">2</badge>
    **The research question**
  </row>
  Can the model predict prices in a GN division it has never seen?
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="info">3</badge>
    **The objectives**
  </row>
  Add hazard data, compare seen versus unseen accuracy, and identify what helps.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="info">4</badge>
    **The data**
  </row>
  7,034 listings, 194 GN divisions, 49 features and 6 hazard variables.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="info">5</badge>
    **The methodology**
  </row>
  Same Random Forest model, two validation approaches: random split and grouped split.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="success">6</badge>
    **The biggest result**
  </row>
  R² falls from 78.97% to 27.90% when predicting unseen divisions.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="success">7</badge>
    **Why it happens**
  </row>
  The model remembers division names instead of learning enough about the actual locations.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="success">8</badge>
    **What works better**
  </row>
  Neighbour prices achieve 45.57% R² on unseen divisions.
  <divider color="subtle"/>
  <row align="center" gap={2}>
    <badge color="info">9</badge>
    **Conclusion**
  </row>
  Describe a location, don't just name it.
</box>

## The five numbers you MUST remember

| Number | Meaning |
|---|---|
| 7,034 | Land listings |
| 194 | GN divisions |
| 78.97% | Seen-division R² |
| 27.90% | Unseen-division R² |
| 45.57% | Neighbour-price R² |

These numbers will help you recover if you forget parts of your speech.

## Let's practise differently

I'll help you prepare like you're actually standing in front of the conference panel.

We'll do **one slide at a time**:
- I'll explain what the slide means in simple English, with Sinhala explanations when useful.
- I'll give you a short, natural speaking version.
- You try saying it without reading.
- I'll correct your answer and move to the next slide.

You don't need to memorise every sentence. You need to understand what you're presenting.

## Start with Slide 1

<AsyncImage query="academic research conference presentation title slide land valuation satellite flood hazard spatial validation Sri Lanka clean blue white presentation" aspectRatio="16:9" maxHeight={150} width="100%" fit="contain"/>

Your opening has just three jobs:

1. Introduce yourself.
2. Introduce your research topic.
3. Explain the main question.

Try saying this naturally:

"Good morning everyone. I'm Kavindu Dilshan from NSBM Green University. Today, I'm presenting our research on automated land valuation in Colombo District.

Our research focuses on one important question: Can a machine learning model accurately predict land prices in an area it has never seen before?"

**Your turn:** Try saying this in your own words. Don't worry about grammar or mistakes. I'll help you improve it.

---

## 🧑 User

slide2

---

## 🤖 ChatGPT

## Slide 2 – Introduction & Problem Statement

<AsyncImage query="academic presentation slide introduction problem statement flood hazard spatial validation land price model two column" aspectRatio="16:9" maxHeight={190} width="100%" fit="contain"/>

This slide explains **two problems in existing land price prediction research.**

### 1. Gap 1 – No hazard variables

**What it means:**

Existing Sri Lankan land price prediction models mainly consider:
- Land size
- Distance to roads
- Nearby facilities and amenities

But they don't include flood-hazard information.

This is important because Colombo experiences flooding.

Examples in your slide:
- Kelani Ganga floods – June 2021
- October 2024
- Cyclone Ditwah – 2025

### 2. Gap 2 – No spatial validation

This is the MOST important part of your research.

Imagine this:

- Your model learns land prices in Kollupitiya.
- During testing, it gets another listing from Kollupitiya.
- It already knows that Kollupitiya is an expensive area.

So the model might get a good prediction simply because it has already seen that location.

But what happens if you give it a completely new GN division?

That's what your research investigates.

### What you should say

<badge color="success">Speaking version</badge>

"There are two main gaps in existing research.

First, existing land price prediction models in Sri Lanka mainly use market and location-related features, but they don't properly consider flood-hazard information. This is important because Colombo frequently experiences flooding.

Second, and more importantly, previous studies mainly use random train-test splitting.

This means listings from the same GN division can appear in both training and testing. As a result, the model may simply remember the price level of an area instead of learning how to predict prices for new areas.

Therefore, our main question is: How accurately can a model predict land prices in a GN division it has never seen before?"

---

### Check your understanding

Let's practise. Don't memorise the paragraph.

**Question:** What are the two main research gaps you identified?

Try answering in your own English. I'll correct it before we move to Slide 3.

---

## 🧑 User

Slide 3

---

## 🤖 ChatGPT

## Slide 3 – Research Objectives

<text color="secondary" size="sm">This slide explains what you wanted to achieve through your research.</text>

Your research has **three main objectives**.

### 1. Add satellite hazard data

You wanted to include flood-hazard and terrain information in the land price prediction model.

For example:
- Elevation
- Distance to rivers
- Flood information from satellite data

**Simple meaning:** Improve the model by adding environmental information.

### 2. Measure seen vs unseen accuracy

You wanted to compare how accurately the model predicts:

- Areas it has already seen during training.
- Completely new GN divisions it has never seen.

Importantly, you kept the same model, features and pipeline. Only the validation method changed.

**Simple meaning:** Find out whether the model really works for new locations.

### 3. Explain the accuracy gap and test improvements

You wanted to understand why accuracy drops when predicting new locations.

You also tested two things:
- Do flood-hazard variables improve predictions?
- Can nearby land prices help predict prices in new divisions?

**Simple meaning:** Understand the problem and find a better way to predict prices in new areas.

---

### 🎤 What you should say

"Based on these research gaps, we identified three main objectives.

First, to integrate satellite-based flood-hazard and terrain variables into a land price prediction model for Colombo District.

Second, to compare model performance between previously seen and completely unseen GN divisions, while keeping the model and features unchanged.

Third, to understand the reason behind the accuracy gap and investigate whether hazard variables or nearby land prices can improve predictions for unseen divisions."

<text color="success" weight="medium" size="sm">Remember these three words:</text>

<box border radius="lg" padding={3} gap={2}>
  <row align="center">
    <title color="default" size="xl">1.</title>
    **ADD** – Satellite hazard data
  </row>
  <divider color="subtle"/>
  <row align="center">
    <title color="default" size="xl">2.</title>
    **COMPARE** – Seen vs unseen accuracy
  </row>
  <divider color="subtle"/>
  <row align="center">
    <title color="default" size="xl">3.</title>
    **IMPROVE** – Test what helps new locations
  </row>
</box>

### Quick practice

Imagine the panel asks:

**"What were the three main objectives of your research?"**

Try answering without looking at the speech. Use ADD, COMPARE and IMPROVE to remember.

---

## 🧑 User

Slide 4

---

## 🤖 ChatGPT

## Slide 4 – Data & Study Area: Colombo District

This slide explains **what data you used to train your model and where the data came from.**

You only need to remember four numbers:

<box border radius="lg" padding={3} gap={3}>
  <grid columns={2} gap={3}>
    <grid-item>
      <title size="2xl" color="#0D9488">7,034</title>
      <text color="secondary" size="sm">Land listings</text>
    </grid-item>
    <grid-item>
      <title size="2xl" color="#0D9488">194</title>
      <text color="secondary" size="sm">GN divisions</text>
    </grid-item>
    <grid-item>
      <title size="2xl" color="#0D9488">49</title>
      <text color="secondary" size="sm">Model features</text>
    </grid-item>
    <grid-item>
      <title size="2xl" color="#0D9488">6</title>
      <text color="secondary" size="sm">Hazard & terrain variables</text>
    </grid-item>
  </grid>
</box>

### 1. Where did the data come from?

You collected 7,034 land listings from Ikman.lk with academic permission.

These listings cover 194 Grama Niladhari (GN) divisions in Colombo District.

The model uses 49 features to predict the **log price per perch**.

Simple meaning:

- A listing is a land property advertised for sale.
- A GN division is a small administrative area.
- A feature is an input used by the machine learning model.
- The target is the land price per perch.

### 2. What are the six hazard variables?

Your research started with 11 hazard and terrain variables. You selected six using predefined screening rules.

The six variables are:

- Elevation
- Surface-water occurrence
- Height above drainage
- Distance to the nearest stream
- Distance to the Kelani Ganga
- Sentinel-1 radar flood maps from three flood events

You don't need to explain every variable in detail during your presentation. Just explain that they describe the environmental and flood-related characteristics of an area.

### 3. The most important limitation

This is the key part of Slide 4.

Your listings do not contain exact land-plot coordinates.

Instead, you assigned the centre point of each GN division to its listings.

Imagine 100 land listings from the same GN division.

Although there are 100 listings, all 100 share the same location point.

Therefore:

**7,034 listings ≠ 7,034 unique locations.**

You only have 194 different location points.

This is important because it explains why your research focuses on GN-division-level spatial validation.

---

### 🎤 Your speaking version

"Our study focuses on Colombo District.

We collected 7,034 land listings from Ikman.lk, covering 194 GN divisions. The model uses 49 features to predict the log price per perch.

We initially considered 11 hazard and terrain variables and selected six using predefined screening rules. These include elevation, surface-water occurrence, drainage-related features, river distances, and Sentinel-1 satellite flood maps.

An important limitation is that the listings do not provide exact plot coordinates. Therefore, we assigned each listing the centre point of its GN division.

So, although we have more than seven thousand listings, we only have 194 unique locations."

---

### Quick practice

Imagine the panel asks:

**"You have 7,034 land listings. Why do you say you only have 194 locations?"**

Try answering in one or two simple sentences.

---

## 🧑 User

slide 5

---

## 🤖 ChatGPT

## Slide 5 – Methodology

This is where you explain **how you conducted your research and how you tested your machine learning model.**

The most important thing to understand is that you used the same Random Forest model but tested it in two different ways.

<AsyncImage query="machine learning spatial cross validation random split versus grouped spatial split train test diagram" aspectRatio="16:9" width="100%" maxHeight={190} fit="contain"/>

### 1. First, understand the pipeline

Your research followed these steps:

1. **Scrape listings** – Collect land advertisements from Ikman.lk.
2. **Match GN divisions** – Identify which GN division each listing belongs to.
3. **Extract hazard values** – Collect environmental and hazard information within a 1 km buffer.
4. **Train Random Forest** – Train the tuned machine learning model.
5. **Test performance** – Compare predictions on seen and unseen divisions.

One important technical detail: price trimming and target encoding were performed inside each training fold to prevent data leakage.

### 2. Two validation methods

This is the most important part of Slide 5.

<box border radius="lg" padding={3} gap={3}>
  **A. Random split – Seen divisions**

  <badge color="warning">Same divisions in training and testing</badge>
  - Randomly split listings into 80% training and 20% testing.
  - Repeated using five different seeds.
  - Listings from the same GN division can appear in both sets.

  Example: Kollupitiya listings can be in both training and testing.

  <divider color="subtle"/>
  **B. Grouped split – Unseen divisions**

  <badge color="success">Entire divisions kept separate</badge>
  - Group listings by GN division.
  - Use GroupKFold with five folds.
  - Repeat with 25 random grouped partitions.
  - A test division is completely excluded from training.

  Example: If Kollupitiya is in the test set, no Kollupitiya listings are used for training.
</box>

### Why did you use two methods?

You wanted to answer two different questions:

- Random split: Can the model predict prices in locations it has already encountered?
- Grouped split: Can the model predict prices in completely new locations?

This comparison helps identify whether the model genuinely learns location characteristics or simply remembers familiar areas.

---

### 🎤 Your speaking version

"Here is our research methodology.

First, we collected the land listings and matched each listing to its corresponding GN division. Then, we extracted environmental and hazard information within a one-kilometre buffer.

Next, we trained a tuned Random Forest model.

To evaluate the model, we used two validation approaches.

The first approach was a random 80/20 train-test split, repeated with five different seeds. In this approach, listings from the same GN division can appear in both training and testing.

The second approach was grouped validation. Here, we grouped listings by GN division, using GroupKFold with five folds and 25 random grouped partitions. This ensures that an entire test division is excluded from training.

This allowed us to compare the model's performance on familiar locations against completely unseen locations."

---

### Remember just three things

<box border radius="lg" padding={3} gap={2}>
  **1. Pipeline**

  Scrape → Match → Extract → Train → Test

  **2. Random split**

  Same GN divisions can appear in training and testing.

  **3. Grouped split**

  Entire GN divisions are kept out of training.
</box>

### Quick practice question

Imagine a panel member asks:

**"What is the main difference between random train-test splitting and grouped spatial validation?"**

Try explaining it in your own words. Don't worry about technical English. I'll help you.

---

## 🧑 User

slide 6

---

## 🤖 ChatGPT

## Slide 6 – Result 1: Accuracy Falls by 51 Points on New Divisions

<text color="secondary" size="sm">This is one of the most important slides in your entire presentation.</text>

The main message is:

**Your model performs well on familiar locations, but its accuracy drops significantly when predicting completely new locations.**

### 1. Understand the two main results

<box border radius="lg" padding={3} gap={3}>
  <grid columns={2} gap={3}>
    <grid-item>
      <title color="#16A34A" size="2xl" tabularNums>78.97%</title>
      **Seen divisions**

      <text color="secondary" size="xs">Random split</text>
    </grid-item>
    <grid-item>
      <title color="#DC6B35" size="2xl" tabularNums>27.90%</title>
      **Unseen divisions**

      <text color="secondary" size="xs">Grouped split</text>
    </grid-item>
  </grid>
  <divider color="subtle"/>
  <title size="2xl" color="danger" tabularNums>51.07 percentage points</title>
  <text color="secondary" size="xs">Drop in R² between seen and unseen divisions</text>
</box>

What does this mean?

- When the model predicts prices in divisions it has already seen, R² is 78.97%.
- When predicting completely new divisions, R² falls to 27.90%.

That's a huge difference.

### 2. What does R² mean?

R² (R-squared) measures how well the model explains variations in land prices.

For your presentation, remember:

- Higher R² means the model explains more of the variation in prices.
- Lower R² means the model explains less.

So 78.97% is much better than 27.90%.

### 3. What about the lighter bars?

Your slide also shows the original global pipeline results:

| Validation | Original pipeline |
|---|---:|
| Seen divisions | 87.72% |
| Unseen divisions | 30.28% |

The important point is that the accuracy gap still exists.

This suggests that the gap is not simply caused by your preprocessing changes.

### 4. What does the 95% interval mean?

Your unseen-division results vary depending on which divisions are selected for testing.

The central 95% of partition results fall between:

- 15.9%
- 38.2%

In simple terms, the model's performance on new locations is unstable.

---

### 🎤 Your speaking version

"This is our first major finding.

We observed a significant difference in model performance between seen and unseen GN divisions.

For previously seen divisions, the model achieved an R-squared of 78.97%.

However, when we tested it on completely unseen divisions, the performance dropped to 27.90%.

That's a reduction of approximately 51 percentage points.

Importantly, we kept the same model, features and pipeline. We only changed the validation design.

We also observed a similar gap using the original global pipeline, with results of 87.72% and 30.28%.

Finally, the unseen results were unstable, with the central 95% of partitions ranging from 15.9% to 38.2%.

This indicates that random-split validation can give an overly optimistic picture of how well a model performs in new locations."

---

### Remember these three things

<box border radius="lg" padding={3} gap={2}>
  **79% → 28%**

  Accuracy drops on unseen divisions.

  **51 percentage points**

  The performance gap.

  **Same model, different validation**

  Only the validation design changed.
</box>

### Quick practice – Panel question

Imagine a researcher asks you:

**"Why do you think the model's R² dropped from 78.97% to 27.90%?"**

Try answering in your own words.

Hint: Think about the difference between familiar and unfamiliar GN divisions.

---

## 🧑 User

side 7

---

## 🤖 ChatGPT

## Slide 7 – Result 2: The Model Remembers the Place

<text color="secondary" size="sm">This slide explains WHY your model performs poorly on completely new GN divisions.</text>

This is probably the most important concept to understand in your research.

**The main message: Your model learned to remember location names instead of learning the actual characteristics of locations.**

### 1. Understand the 75.40%

<box border radius="lg" padding={3} gap={1}>
  <title size="2xl" color="#0D9488" tabularNums>75.40%</title>
  **Gini importance**

  <text color="secondary" size="sm">Comes from one feature: target-encoded division name (Address_target_enc).</text>
</box>

What is target encoding?

Imagine your dataset contains these divisions:

| GN division | Average land price |
|---|---:|
| Kollupitiya | High |
| Bambalapitiya | High |
| Homagama | Lower |

Instead of giving the model just the division name, target encoding converts the name into a numerical value based on the average price in the training data.

For example:
- Kollupitiya → its average training price.
- Homagama → its average training price.

The model can use these values to predict land prices.

### 2. Why does this become a problem?

Look at the right side of your slide.

<box border radius="lg" padding={3} gap={3}>
  **Seen divisions**

  <badge color="success">Rank #1</badge>

  The encoded division name is the most important feature according to permutation importance.

  <divider color="subtle"/>
  **Unseen divisions**

  <badge color="danger">Rank #34 out of 49</badge>

  Its R² importance drop is 0.0000.

  This means removing that feature does not change the model's R² on unseen divisions.
</box>

Why?

Imagine the model has already seen Kollupitiya during training.

It knows Kollupitiya's encoded price information.

But now you give it a completely new GN division.

The encoder has never seen that division before, so it assigns the overall training average.

Therefore, the feature cannot distinguish that new division from other unseen divisions.

**This is called the location-identity problem.**

### 3. Understand the difference

- Naming a location: Kollupitiya, Homagama, Maharagama.
- Describing a location: elevation, distance to rivers, nearby facilities and environmental characteristics.

Your model relied heavily on naming the location rather than describing it.

---

### 🎤 Your speaking version

"After identifying the accuracy gap, we investigated why this happens.

We found that one feature, the target-encoded GN division name, contributes 75.40% of the model's Gini importance.

In the seen-division evaluation, this feature is ranked number one in permutation importance.

However, for unseen divisions, its importance drops to number 34 out of 49, with an R-squared change of zero when removed.

The reason is that when the model encounters a new GN division, the target encoder has no previously learned value for that division. Instead, it assigns the overall training average.

Therefore, this feature cannot provide useful information for distinguishing new locations.

We call this the location-identity problem. In simple terms, the model learned to name the place rather than describe it."

---

### Remember these four things

<box border radius="lg" padding={3} gap={2}>
  **75.40%** – Gini importance from division identity.

  **#1** – Permutation rank on seen divisions.

  **#34** – Permutation rank on unseen divisions.

  **0.0000** – R² change when removing the feature on unseen divisions.
</box>

### Quick practice – Important panel question

**"What exactly do you mean by the location-identity problem?"**

Try explaining it using the Kollupitiya example.

Don't worry about perfect English. I want to make sure you understand the concept, not memorise my paragraph.

---

## 🧑 User

slide 8

---

## 🤖 ChatGPT

## Slide 8 – Result 3: What Helps on Unseen Divisions?

<text color="secondary" size="sm">This slide explains what you tested to improve predictions for completely new locations.</text>

The main message is:

**Neighbouring land prices help predict new locations better than the original Random Forest model.**

### 1. Understand the results

Your slide compares five different approaches.

<box border radius="lg" padding={3} gap={3}>
  <title size="2xl" color="#16A34A" tabularNums>45.57%</title>
  **Neighbour price only (K = 5)**

  <badge color="success">Best result</badge>
  <text color="secondary" size="sm">Highest R² on unseen divisions.</text>
  <divider color="subtle"/>
  <title size="xl" tabularNums>41.98%</title>
  **Random Forest + neighbour price, without identity feature**
  <divider color="subtle"/>
  <title size="xl" tabularNums>29.73%</title>
  **Random Forest + neighbour price**
  <divider color="subtle"/>
  <title size="xl" tabularNums>27.90%</title>
  **Original Random Forest**
  <divider color="subtle"/>
  <title size="xl" tabularNums>27.53%</title>
  **Random Forest without hazard variables**
</box>

### 2. What is neighbour price?

This is important to understand.

Imagine you want to predict the land price in a new GN division.

You don't have previous land-price information for that division.

But you have information about nearby divisions.

For example:

- Nearby division A – average price.
- Nearby division B – average price.
- Nearby division C – average price.
- Nearby division D – average price.
- Nearby division E – average price.

You calculate a weighted average of these five divisions' prices.

The closer divisions receive more weight than the further divisions.

This is called **Inverse-Distance-Weighted (IDW) neighbour price**.

In simple terms, you use the prices of nearby known areas to estimate the price of a new area.

### 3. What did you discover?

Your original Random Forest achieved 27.90%.

Neighbour price alone achieved 45.57%.

That's an improvement of 17.67 percentage points.

Importantly, neighbour price performed better in all 25 partitions.

You also tested adding neighbour price to the Random Forest.

- Keeping the identity feature: 29.73%.
- Removing the identity feature: 41.98%.

This tells us that the location identity feature was not helping the model generalise to new divisions.

### 4. What about hazard variables?

You also tested what happens when you remove all six hazard variables.

- Original Random Forest: 27.90%.
- Without hazard variables: 27.53%.
- Difference: -0.37 percentage points.

The 95% confidence interval was -0.74 to -0.01.

According to your predefined decision rule, this did not pass the threshold.

Therefore, the hazard variables showed only a small, non-robust effect in this experiment.

**Important:** Don't say flood hazards are unimportant in general. Your result only shows that these six variables added little predictive value in this particular Colombo dataset and experimental setup.

---

### 🎤 Your speaking version

"After identifying the location-identity problem, we investigated what could improve predictions for unseen divisions.

First, we tested the contribution of the six hazard variables. Removing all six resulted in a small decrease of 0.37 percentage points, which did not pass our predefined decision rule. Therefore, their contribution was small and not robust.

Next, we tested neighbour price. This is calculated using the inverse-distance-weighted average price of the five nearest training divisions.

Neighbour price alone achieved an R-squared of 45.57%, which is 17.67 percentage points higher than our original Random Forest model. It also performed better in all 25 partitions.

We further tested combining neighbour price with the Random Forest. When we removed the location-identity feature, performance improved to 41.98%.

These results suggest that describing a location through its neighbouring areas is more useful than simply identifying it by name."

---

### Remember these five things

<box border radius="lg" padding={3} gap={2}>
  **45.57%** – Neighbour price alone.

  **27.90%** – Original Random Forest.

  **+17.67 points** – Improvement from neighbour price.

  **41.98%** – Random Forest without identity + neighbour price.

  **-0.37 points** – Effect of removing hazard variables.
</box>

### Quick practice – Panel question

Imagine a panel member asks:

**"What is neighbour price, and why did it perform better than your Random Forest model?"**

Try explaining it using a simple example of five nearby GN divisions.

Don't worry about perfect English. Focus on explaining how the method works.

---

## 🧑 User

slide 9

---

## 🤖 ChatGPT

## Slide 9 – Conclusion & Future Work

<text color="secondary" size="sm">This is your final research slide. Your job is to remind the panel what you discovered and leave them with one strong message.</text>

### 1. Four main conclusions

Your research has four important findings.

**1. Random split gives an overly optimistic result.**

The model achieved approximately 79% R² on seen divisions but only 28% on unseen divisions.

Meaning: We cannot rely only on random train-test splitting to evaluate land price models.

**2. Studies should report both results.**

Land valuation research should evaluate performance on:
- Seen GN divisions.
- Unseen GN divisions.

Meaning: Researchers should test whether their models can generalise to new geographical areas.

**3. Hazard variables added very little.**

Your six satellite flood-hazard and terrain variables provided only a small, non-robust contribution in this experiment.

Meaning: Including satellite data does not automatically improve prediction accuracy.

**4. Neighbour prices work better for new locations.**

Neighbour price achieved 45.57% R², compared with 27.90% for the original Random Forest.

Meaning: Nearby geographical information can be useful when predicting prices in new areas.

---

### 2. Future work

Your research also identifies three areas for improvement.

<box border radius="lg" padding={3} gap={3}>
  **1. SAR coherence**

  Improve flood detection in built-up areas using Synthetic Aperture Radar (SAR) coherence.

  <divider color="subtle"/>
  **2. Plot-level geocoding**

  Obtain exact land-plot coordinates instead of using GN-division centre points. This could allow spatial methods such as kriging.

  <divider color="subtle"/>
  **3. Better datasets**

  Collect real land listings from high-hazard districts such as Ratnapura and, ideally, actual transacted prices.
</box>

### 🎤 Your speaking version

"To conclude, our research produced four main findings.

First, random-split validation can give an overly optimistic picture of model performance, with approximately 79% accuracy on seen divisions compared to 28% on unseen divisions.

Second, land valuation studies should report both seen-division and unseen-division performance.

Third, the satellite flood-hazard variables provided only a small and non-robust improvement in our Colombo experiment.

Fourth, neighbour prices provided the best location information for predicting prices in new areas.

For future work, we plan to explore SAR coherence for better flood detection in built-up areas, improve plot-level geocoding, and collect real property data from high-hazard districts such as Ratnapura.

Our main message is simple: **Describe a location, don't just name it.**"

---

### 3. Your most important final sentence

<box background="surface" radius="lg" padding={3} gap={2}>
  <title size="xl" textAlign="center">"Describe a location, don't just name it."</title>
  <text color="secondary" textAlign="center" size="sm">Pause briefly before saying this. Look at the panel.</text>
</box>

This sentence connects your entire research:
- The location-identity problem.
- The accuracy gap.
- The importance of neighbouring prices.
- The need for better geographical information.

### Quick practice

Imagine the panel asks:

**"What is the main contribution of your research?"**

Try answering in 2–3 sentences using your own words.

Don't memorise the entire conclusion. Understand the four findings and finish confidently.

---

## 🧑 User

What is log price per perch mean

---

## 🤖 ChatGPT

**Log price per perch** means the land price per perch is converted into a logarithmic value before training the machine learning model.

Let's break it down:

- **Price per perch:** How much one perch of land costs. For example, LKR 1,000,000 per perch.
- **Log price:** Instead of using the original price directly, we apply a mathematical function called the natural logarithm (`ln`) to that price.

**Why did we use log price?**

Land prices can vary significantly. For example, one property might cost LKR 500,000 per perch, while another costs LKR 10 million. Taking the log helps reduce this large difference and makes the price data easier for the model to work with.

**Simple answer for your presentation:**

> "Log price per perch means we apply a natural logarithm to the land price per perch. We do this to reduce the effect of very large price differences and make the data more suitable for machine learning."

Remember: the model predicts the **log-transformed price**, not the original price directly.
