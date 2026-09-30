<img src="portal/logo.svg" alt="" width="64">

# Yuan

A private job search tracker that you run with Claude, on your own computer.
It helps you get clear on what you want, keeps your applications in one place,
checks in when things change and, if you like, finds roles and drafts cover
letters for you to review. It never applies for you.

缘 (yuán) is the connection between people who are meant to meet. Written another
way, 元, it's money.

## Get started

1. **Answer the setup questions** at **[yuan-hazel.vercel.app](https://yuan-hazel.vercel.app)** (about 15 to 20 minutes;
   only your name and one job title are required). At the end you download
   one folder with your answers and your resume. The page sends nothing
   anywhere.
2. **Install Claude Code** if you don't have it (it uses your Claude account).
   On a Mac or Linux, open Terminal and paste:
   ```
   curl -fsSL https://claude.ai/install.sh | bash
   ```
   On Windows, install WSL first and run it there.
3. **Open the folder with Claude.** Unzip it, move it somewhere permanent
   (like your home folder), then:
   ```
   cd ~/your-name-job-search
   claude
   ```
   Say hi. Claude builds your tracker from your answers and walks you through
   a short first session. It helps install anything else it needs (Python,
   Postgres) and asks before installing anything.

## What you get

- A dashboard of your applications at http://localhost:8420/.
- Claude as a guide: tell it what happened ("I applied to Acme", "they want
  a call Thursday") and it keeps the tracker up to date. It helps you think
  through offers against what you said matters most, and checks in when
  something changes.
- Optionally, a job finder that searches public job listings (company job
  boards, Y Combinator, Hacker News, the web) once a day and drafts cover
  letters for strong matches. You review and apply yourself.
- A resume builder that rewrites your resume from your own stories, with
  your OK at every step.

## Your data

Your tracker, answers and resume stay in that folder on your computer.
Claude reads them with your own Claude account when you work with it, and the
job finder reads public job listings. Nothing logs in, submits or creates
accounts for you.

## Other ways to set it up

Prefer not to use the page? Install the setup skill and run it in an empty
folder:

```
curl -fsSL https://raw.githubusercontent.com/eboxyz/yuan/main/install.sh | bash
mkdir ~/job-search && cd ~/job-search && claude
```

Then type `/tracker-setup`. If an `intake.json` from the setup page is in the
folder, it uses your answers; otherwise it sets up a job search tracker with
sensible defaults. It can also build trackers for other searches (apartments,
grad school, sales leads).

## More

[How it works](docs/technical.md) · [Setup answers](docs/intake.md) ·
[How this was built](docs/how-it-was-built.md) · [License](LICENSE)
