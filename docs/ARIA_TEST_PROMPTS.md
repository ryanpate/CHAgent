# Aria RAG Test Prompts

This document provides comprehensive prompts to test and validate the Aria AI assistant's RAG (Retrieval-Augmented Generation) capabilities. Use these prompts to verify functionality, identify issues, and improve response quality.

---

## How to Use This Document

1. **Manual Testing**: Work through each category, noting success/failures
2. **Regression Testing**: Run after code changes to ensure no regressions
3. **Training Data**: Successful prompts can inform system prompt improvements
4. **Edge Case Discovery**: Failed prompts highlight areas needing improvement

### Rating Scale
- ✅ **Pass**: Correct response with relevant data
- ⚠️ **Partial**: Correct intent, incomplete/imprecise data
- ❌ **Fail**: Wrong data, wrong interpretation, or error

---

## 1. Volunteer Information Queries

### 1.1 Contact Information

**Basic Contact Lookup**
```
What's John Smith's email?
How can I reach Sarah Johnson?
What's the contact info for Mike Davis?
David's phone number
Get me Lisa's email address
```

**Variations & Edge Cases**
```
What is strucks contact info?           # Possessive without apostrophe
Do you have Emma's phone?               # Informal possessive
How do I get in touch with the Smiths?  # Plural family name
Contact details for david               # Lowercase name
What's john smith's email address?      # Lowercase full name
```

**Expected Behavior**:
- Should search Planning Center for person
- Return email/phone if available
- Handle first-name-only with disambiguation

### 1.2 Personal Details

**Family Information**
```
Does Sarah have kids?
What are Mike's kids' names?
Is John married?
Tell me about Lisa's family
Who is David's spouse?
```

**Hobbies & Interests**
```
What are Sarah's hobbies?
What does John like to do for fun?
Does Mike have any interests outside of church?
What's Lisa into?
```

**Birthday & Anniversary**
```
When is John's birthday?
What's Sarah's birth date?
When was Mike born?
How old is David?
When is Lisa's anniversary?
```

**Expected Behavior**:
- Pull from extracted knowledge (interactions)
- Fall back to Planning Center if available
- Acknowledge when information is unknown

### 1.3 Service History

**Past Service**
```
When did John last serve?
When was Sarah's last time playing?
When did Mike play most recently?
Show me David's service history
```

**Future Schedule**
```
When does Sarah play next?
Is John scheduled this Sunday?
When is Lisa serving next?
Is Mike on the team this week?
```

**Expected Behavior**:
- Query Planning Center Services API
- Handle both past and future queries
- Support various tense patterns

---

## 2. Schedule & Team Queries

### 2.1 Team Schedule (Who's Serving)

**This Sunday**
```
Who's on the team this Sunday?
Who is serving this week?
Who's playing this Sunday?
What's the team for this Sunday?
Who do we have this weekend?
```

**Past Sundays**
```
Who was on the team last Sunday?
Who served on Easter?
Who played on December 14th?
What was the team on 11/16?
Who was serving last week?
```

**Future Sundays**
```
Who's scheduled for next Sunday?
Who is on the team for Christmas Eve?
What's the schedule for December 21st?
Who's playing next week?
```

**Service Type Variations**
```
Who's on the HSM team this Sunday?      # High School Ministry
Who's serving MSM this week?             # Middle School Ministry
Who's on the youth team?
Who's playing for high school?
```

**Expected Behavior**:
- Query correct service type (default: main, HSM/MSM if keywords present)
- Format team list clearly by position
- Handle various date formats

### 2.2 Blockouts & Availability

**Person-Specific Blockouts**
```
When is Sarah blocked out?
What are John's blockout dates?
Show me Mike's blockouts
Is Lisa blocked out this month?
```

**Date-Specific Blockouts**
```
Who's blocked out on December 14th?
Who can't make it this Sunday?
Who has blockouts for Christmas Eve?
Who's unavailable next week?
```

**Availability Checks**
```
Is John available on December 21st?
Can Sarah serve this Sunday?
Is Mike free for Christmas Eve?
Check Lisa's availability for 12/28
```

**Team Availability**
```
Team availability for this Sunday
Who's available next week?
Show me availability for December 14th
Who can serve on Christmas?
```

**Expected Behavior**:
- Query Planning Center blockouts
- Cross-reference with schedule
- Handle rate limits gracefully (many API calls)

---

## 3. Song & Setlist Queries

### 3.1 Setlist Lookup

**Recent Services**
```
What songs did we play last Sunday?
Show me the setlist from last week
What did we sing on Easter?
What songs were on the set on 11/16?
What did we play on Christmas Eve?
```

**Date Formats**
```
Setlist for November 16th, 2024
Songs from 11/16
What did we play on 11-16-2024?
Set from last Sunday
```

**Expected Behavior**:
- Find correct service plan
- List songs in order
- Include keys if available

### 3.2 Song History

**When Was Song Played**
```
When did we last play Gratitude?
When was the last time we did Way Maker?
Have we ever played Oceans?
How often do we play Build My Life?
When did we use Amazing Grace?
```

**Song Usage Patterns**
```
Song usage history for Holy Spirit
How many times have we played Great Are You Lord?
Show me the history for Goodness of God
When's the last time we did 10,000 Reasons?
```

**Expected Behavior**:
- Search song library by title
- Return usage history with dates
- Handle partial title matches

### 3.3 Chord Charts & Lyrics

**Chord Chart Requests**
```
Chord chart for Goodness of God
Get me the chords for Way Maker
Lead sheet for Great Are You Lord
Charts for Build My Life
Show me the chord chart for Amazing Grace
```

**Lyrics Requests**
```
Show me the lyrics for Holy Spirit
What's the chorus of Way Maker?
Lyrics to the bridge of Gratitude
What are the words to Amazing Grace?
Give me the lyrics for Oceans
```

**Section-Specific**
```
Lyrics to the chorus of Goodness of God
Show me verse 2 of Way Maker
What's the bridge of Build My Life?
Pre-chorus lyrics for Great Are You Lord
```

**Expected Behavior**:
- Search PCO attachments
- Return content or link to file
- Handle section requests

### 3.4 Song Information

**Key & Tempo**
```
What key is Goodness of God in?
What's the BPM for Way Maker?
How fast is Build My Life?
What tempo is Great Are You Lord?
Which key do we do Holy Spirit in?
```

**Expected Behavior**:
- Return song metadata from PCO
- Include common arrangements

---

## 4. Interaction Logging

### 4.1 Basic Logging

**Simple Interactions**
```
Log interaction: Talked with Sarah after service. She seemed tired but happy.
Log: Had coffee with John. He mentioned his daughter is starting college.
Note: Saw Mike at the grocery store. His wife just had a baby.
Record: Lisa called about the upcoming schedule.
```

**Detailed Interactions**
```
Log interaction: Met with David before rehearsal. He's dealing with some stress at work - his company is going through layoffs. He asked for prayer for job security. His son just turned 5 and loves dinosaurs. We talked about possibly joining the production team in spring.
```

**Expected Extraction**:
- Volunteer name: David
- Prayer request: Job security (work layoffs)
- Family: Son, age 5, likes dinosaurs
- Interest: Production team (spring)
- Follow-up: Check in about work situation

### 4.2 Multi-Volunteer Interactions

```
Log: Group dinner with Sarah, John, and Mike. Sarah mentioned her mom is visiting next week. John is training for a marathon. Mike just got promoted at work.
```

**Expected Behavior**:
- Link all three volunteers
- Extract facts for each
- Create appropriate follow-ups

### 4.3 Follow-up Detection

**Explicit Follow-ups**
```
Log: Talked with Sarah. She asked if I could check in with her next week about her mom's surgery.

Log: John mentioned he'd like to discuss joining the worship team. Need to follow up in January.
```

**Implicit Follow-ups**
```
Log: Lisa seemed really down today. Her dog passed away last week.

Log: Mike is stressed about his upcoming presentation at work.
```

**Expected Behavior**:
- Create FollowUp objects when appropriate
- Set reasonable follow-up dates
- Categorize correctly (prayer, action, check-in)

---

## 5. Analytics & Reporting Queries

### 5.1 Team Overview

**General Stats**
```
Team overview
How are we doing as a team?
Give me team stats
Team summary
Show me the dashboard
```

**Expected Response**:
- Total volunteers
- Recent interaction count
- Pending follow-ups
- Care needs summary

### 5.2 Volunteer Engagement

**Engagement Reports**
```
Volunteer engagement report
Who are our most engaged volunteers?
Which volunteers need attention?
Show me least active volunteers
Engagement trends
```

**Expected Response**:
- Most/least engaged lists
- Interaction counts
- Days since last contact

### 5.3 Care & Follow-up Reports

**Care Needs**
```
Who needs a check-in?
Show me volunteers I should reach out to
Who should I follow up with?
Care priorities for this week
Overdue follow-ups
```

**Proactive Care**
```
Proactive care dashboard
Care alerts
What should I focus on today?
Who needs attention?
Care insights
```

**Expected Response**:
- Overdue follow-ups
- Volunteers with no recent contact
- Upcoming birthdays/anniversaries
- Prayer request follow-ups

### 5.4 Prayer Requests

**Prayer Summaries**
```
Prayer request summary
What are people praying about?
Common prayer themes
Show me recent prayer requests
Who needs prayer?
```

**Expected Response**:
- Aggregated themes
- Recent requests
- Volunteer attribution

### 5.5 AI Performance

**Aria Stats**
```
How is Aria doing?
AI performance stats
Feedback summary
Aria accuracy
```

---

## 6. Disambiguation Scenarios

### 6.1 Song vs Person

**Ambiguous Queries**
```
When did we last play Gratitude?        # Song "Gratitude" or person?
Have we played Grace recently?          # Song or person named Grace?
When was Joy last on the schedule?      # Song "Joy" or volunteer Joy?
```

**Expected Behavior**:
- Detect ambiguity
- Ask for clarification: "Are you asking about the song 'Gratitude' or a person named Gratitude?"
- Handle response correctly

**User Clarification Responses**
```
The song                    # After disambiguation
It's a song                 # After disambiguation
I mean the person          # After disambiguation
The volunteer              # After disambiguation
```

### 6.2 First Name Disambiguation

**First Name Only**
```
When does Sarah play next?              # If multiple Sarahs
What's John's email?                    # If multiple Johns
Lisa's blockout dates                   # If multiple Lisas
```

**Expected Behavior**:
- Present list of matching people
- "I found 3 people named Sarah: Sarah Johnson (Vocals), Sarah Smith (Band)..."
- Ask which one they mean

### 6.3 Date Confusion

**Relative Dates**
```
What songs did we play on Sunday?       # Which Sunday?
Who served last week?                   # Specific date needed?
Show me the setlist from that service   # No context
```

**Expected Behavior**:
- Assume most recent if unclear
- Ask for clarification if truly ambiguous

---

## 7. Error Handling & Edge Cases

### 7.1 Not Found Scenarios

**Person Not Found**
```
What's Xyzzy McFakename's email?
When does Nonexistent Person serve?
Contact info for Someone Who Doesn't Exist
```

**Song Not Found**
```
Chord chart for Made Up Song Title
When did we play Nonexistent Song?
Lyrics for A Song We've Never Done
```

**Date Not Found**
```
Who served on January 1st, 1900?
Setlist for next year
Schedule for yesterday                  # If no service
```

**Expected Behavior**:
- Clear "not found" message
- Suggest similar names if close matches exist
- Don't hallucinate data

### 7.2 Permission & Access

**Limited Access**
```
Show me billing information             # Shouldn't be accessible via chat
Admin settings                          # Shouldn't be accessible via chat
Delete all volunteers                   # Destructive action
```

**Expected Behavior**:
- Politely decline
- Redirect to appropriate UI

### 7.3 Malformed Input

**Typos & Misspellings**
```
Waht's johns emial?                    # Typos
Shwo me teh setlsit                    # Typos
who's servng on sundya?                # Typos
```

**Grammar Issues**
```
john email?                            # Missing possessive
when sarah serve next                  # Missing auxiliary verb
songs last sunday what                 # Unusual word order
```

**Expected Behavior**:
- Attempt to understand intent
- Provide reasonable response
- Ask for clarification if truly incomprehensible

### 7.4 Context Dependency

**Follow-up Questions**
```
User: What's Sarah's email?
Aria: [responds with email]
User: What about her phone?            # Should maintain "Sarah" context

User: Who served last Sunday?
Aria: [responds with list]
User: What songs did they play?        # Should know "they" = that team
```

**Expected Behavior**:
- Maintain conversation context
- Resolve pronouns correctly
- Handle "her", "his", "they", "that" references

---

## 8. Multi-Turn Conversations

### 8.1 Progressive Information Gathering

```
User: I need to check in with someone
Aria: I can help with that! Who would you like to check in with?
User: Sarah
Aria: I found Sarah Johnson and Sarah Smith. Which one?
User: The vocalist
Aria: Got it, Sarah Johnson. What would you like to know about her?
User: When did I last log an interaction with her?
```

### 8.2 Task Completion Flows

**Follow-up Creation**
```
User: I need to follow up with John
Aria: What would you like to follow up about?
User: His job situation
Aria: When should I remind you?
User: Next week
Aria: Created: "Follow up with John about job situation" for [date]
```

**Interaction Logging**
```
User: Log an interaction
Aria: Who did you talk with?
User: Mike Davis
Aria: What would you like to note about your conversation?
User: He's stressed about his upcoming surgery
Aria: [Creates interaction, extracts prayer request, offers follow-up]
```

---

## 9. Aggregate & Team-Wide Queries

### 9.1 Food & Preferences

```
What are everyone's favorite foods?
Show me all dietary restrictions on the team
What food preferences do we have recorded?
Does anyone have food allergies?
```

### 9.2 Hobbies & Interests

```
What hobbies do our volunteers have?
Who likes hiking?
Show me volunteers interested in photography
What are the most common hobbies on our team?
```

### 9.3 Family Information

```
How many volunteers have kids?
Who has birthdays this month?
Show me all upcoming anniversaries
Which volunteers are married?
```

### 9.4 Availability Patterns

```
Who's usually available on Sundays?
Which volunteers travel frequently?
Who has the most blockouts this month?
Show me overall team availability
```

---

## 10. Stress Testing

### 10.1 Long Queries

```
I need to find out when John Smith who plays guitar in the band and sometimes fills in on bass when David is out of town because of his work travel which happens a lot in the fall especially around October and November when his company has their annual conferences is scheduled to serve next and also if he has any conflicts with the Christmas Eve service because I remember he mentioned something about possibly traveling to visit his parents in Florida.
```

### 10.2 Multiple Topics

```
What's John's email, when does Sarah serve next, and what songs did we play on Easter?
```

### 10.3 Rapid-Fire Questions

```
John's email?
Sarah's schedule?
Last Sunday's setlist?
Who's blocked out tomorrow?
Mike's birthday?
```

---

## 11. Comparative & Trend Queries

### 11.1 Time Comparisons

```
Are we logging more interactions this month than last?
How does volunteer engagement compare to last quarter?
Are we playing more new songs lately?
```

### 11.2 Volunteer Comparisons

```
Who logs the most interactions?
Which volunteer serves most frequently?
Who has the most follow-ups pending?
```

---

## 12. Documentation for Continuous Improvement

### Test Session Template

```markdown
## Test Session: [Date]
**Tester**: [Name]
**Version**: [Git commit or version]

### Tests Run: [X] / [Total]
### Pass Rate: [X%]

### Critical Failures:
1. [Prompt] → [Expected] vs [Actual]

### Partial Failures:
1. [Prompt] → [Issue description]

### New Edge Cases Discovered:
1. [Description]

### Improvement Suggestions:
1. [Suggestion]
```

### Issue Tracking

When a test fails, document:
1. **Prompt**: Exact input
2. **Expected**: What should happen
3. **Actual**: What did happen
4. **Query Detection**: Was the query type correctly identified?
5. **Data Retrieval**: Was the right data fetched?
6. **Formatting**: Was the response well-formatted?
7. **Suggested Fix**: How to improve

---

## Appendix: Query Type Reference

| Query Type | Detection Function | Key Patterns |
|------------|-------------------|--------------|
| Aggregate | `is_aggregate_question()` | "entire team", "all volunteers", "most common" |
| Analytics | `is_analytics_query()` | "team overview", "engagement", "care needs" |
| PCO Data | `is_pco_data_query()` | "email", "phone", "birthday", "when does X serve" |
| Blockouts | `is_blockout_query()` | "blocked out", "available", "can X serve" |
| Songs | `is_song_or_setlist_query()` | "setlist", "chord chart", "lyrics", "what songs" |
| Ambiguous | `check_ambiguous_song_or_person()` | "when did we play X" (X could be song or person) |
| Interaction Log | Keywords | "log:", "log interaction:", "note:" |
| Follow-up | Context | "follow up", "remind me", after logging |
