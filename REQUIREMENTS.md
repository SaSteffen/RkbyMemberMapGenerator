Team Rynkeby Hamburg Team Map Tool
====

Purpose, general idea
---

We are the Team Rynkeby Hamburg charity cycling team.

We are a group of people coming from a relatively wider area around Hamburg, Germany. Since that area is relatively wide, we want to find ways to help people connect with each other.
At the start of each season there are always a bunch of old and new faces, and we want to effectively connect the old and the new ones.

We have different Roles in the team. Primary Roles are: Rider, Service Crew Member, Supporter. 

Riders are people who take part in the ride to Paris in July. (Happens every year) The service Crew is there to support the riders with their luggage and food supply during the tour and trainings. 

- I want to create maps (photo graphics, maybe shareable interactive map with zoom control) that gives everyone an idea about where everyone lives, who might be a neighbor, possible training partner.
- I want to find pairings of experienced and inexperienced riders, primarily based on their location and number of seasons they have participated in team rynkeby.
- i want to create a calendar file with all the birthdays of team members that we can import into a calendar to remind us of erverone's birthdays


Technical considerations
--

The Team Data is located in the so called "Team Rynkeby Intranet" which is a website.
The data includes this information for each team member:

- Name
- address
- photo
- phone number
- birthday

We want to scrape that data and use it as the basis for further processing, since information might be incorrect/spotty. Therefore we will store the data (locally) and manually improve it (change photo, fix birthday, add adress etc.).

I want to create several Python based scripts, that can create the individual target artifacts I described above.