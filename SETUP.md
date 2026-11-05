# How to set up Boligvagt

Boligvagt ("housing watch") checks 11 Danish rental websites around the clock and
notifies your phone within a few minutes when a home that fits you appears.
You don't need to code. Everything happens in the browser and on your phone.

**Time: about 30 minutes.** You need an iPhone and a computer.

**Is someone running Boligvagt for you?** Then you only need
[START-HERE.md](START-HERE.md). The person running it reads
*Running Boligvagt for someone else* at the end of this guide.

Many of the websites are in Danish. **GOOD-TO-KNOW.md** has a short list of the
Danish words you will meet in listings (aconto, depositum, st. tv. …).

## Part 1: Pushover on your phone (about 10 min)

Pushover is the app that delivers the notifications. It is free for 30 days and
then costs $4.99 once.

1. Install **Pushover** from the App Store and open it.
2. Tap **Create an account** and sign up with your email. Confirm your email.
3. When the app asks to send notifications, tap **Allow**. Then, in the app, open
   **Settings** and under **Alert Settings**:
   - Turn **on** **Critical Alerts for emergency-priority**. If the iPhone asks
     for permission, tap **Allow**. This makes your most important homes ring
     even when the phone is on silent.
   - Leave **Critical Alerts for high-priority** **off**. Otherwise every home
     breaks through silent mode, also at night.
4. On your computer: go to **pushover.net** and log in.
5. At the top right you see **Your User Key**. Copy it into a note. This is your
   *user key*.
6. Scroll down and click **Create an Application/API Token**.
   - **Name**: Boligvagt
   - Tick the box to accept the terms and click **Create Application**.
   - Copy the **API Token/Key** into your note. This is your *app key*.

## Part 2: Your own Boligvagt on GitHub (about 15 min)

> ⚠️ **Use a GitHub account only for Boligvagt.** GitHub's terms say its servers
> are for building and testing software. A watcher running around the clock is
> outside that, so GitHub can stop it and, in some cases, close the account. If
> you already use GitHub for work, study or your own code, don't use that
> account here. More in **GOOD-TO-KNOW.md** → *Which accounts can be closed?*

7. Create a new, free account on **github.com** (click **Sign up**).
   - If you already have a GitHub account, sign up with a different email
     address. GitHub allows one extra account per person for automated tasks,
     as long as it is used only for that.
   - Choose a username that isn't your name. Your Boligvagt is public, so anyone
     can see the username and your search settings (not your keys or your
     message).
8. Send your GitHub username to Simon. He sends you an invitation by email: open
   it and click **Accept invitation**.
9. Go to **github.com/simon-jensen/boligvagt**. Click the green button
   **Use this template** → **Create a new repository**.
   - **Repository name**: boligvagt
   - Leave **Include all branches** unticked. Then your Boligvagt starts with an
     empty memory and doesn't send you all the homes that already exist.
   - Choose **Public**. It must be public, because then running around the
     clock is free. Your keys and your message stay secret (step 10).
   - Click **Create repository**.
10. In your new boligvagt: click **Settings** → **Secrets and variables** →
    **Actions** → **New repository secret**. Create two secrets:
    - **Name** `PUSHOVER_USER`, **Secret**: your user key from step 5 → **Add secret**.
    - **Name** `PUSHOVER_TOKEN`, **Secret**: your app key from step 6 → **Add secret**.
11. Click **Actions** at the top. If GitHub asks whether to enable workflows,
    click the green button.
12. Put your phone on silent. Then click **Send test message** in the list on the
    left → **Run workflow** → **Run workflow**. Within a minute you get two
    messages: an example of a home, and a test that rings every minute until you
    open it in the Pushover app and tap **Acknowledge Notification** at the bottom.
    That is how your most important homes will ring. If the phone doesn't ring on
    silent, see problem 2 below.
13. Click **Watch for homes** in the list on the left → **Run workflow**. Leave
    the number of minutes at **60** (each run lasts an hour and starts the next
    one by itself) and click **Run workflow**. Within a few minutes you get the
    message **Boligvagt has started**.

That's it – it now runs by itself. Every Monday at 9:00 you get a silent message
saying it is still running.

**Tip:** Also create a free saved search ("søgeagent") in the Boligportal app as
a backup. The app is available in English.

## How to change your search

1. Open your boligvagt on GitHub and click the file **settings.toml**.
2. Click the pencil (✏️) at the top right.
3. Change the values. Every setting is explained in the file, including which
   postal code is which area. Write numbers without dots or "kr", e.g. `13000`.
4. Click **Commit changes** → **Commit changes**.

Boligvagt uses the new settings within 10 minutes. If you make a mistake, you
get a message saying what is wrong, and the previous settings are kept meanwhile.

The same file decides when your phone rings (the `[[priority]]` blocks).

## Automatic contact with the landlord (optional)

On CEJ and Kereby, Boligvagt can write to the landlord for you the moment a home
appears. It sends your own text with the home's address and move-in date filled in.

> ⚠️ **It writes in your real name.** No account is involved, so nothing can be
> closed, but a landlord who notices automatic messages may ignore you. A
> separate email doesn't help, because the landlord must be able to reach you.
> So try it in "test" first, write a personal message, and keep `max_per_day` low.

1. Open the file **applicant.example.toml** and copy all of it.
2. Fill in your details and your message (see **MESSAGE-TEMPLATE.md**).
   Everything written in `<...>` must be replaced. The Danish choices for CEJ
   are explained in the file.
3. Save it as a secret like in step 10: **Name** `APPLICANT`, and paste in all
   the text.
4. Try it first: **Actions** → **Try auto-contact** → **Run workflow**, and paste
   the link to an available home on CEJ or Kereby. You get a picture of the
   filled-in form on your phone. Nothing is sent.
5. When the picture looks right: set `CEJ` and `Kereby` to `"test"` in
   **settings.toml**. Then you get a picture every time a home matches.
6. Only when you trust it: change them to `"send"`. Then the message is sent in
   your name.

## The five most likely problems

**1. The test message doesn't arrive.**
Open **Actions** → **Send test message** → the top run → **test**.
- If it says "The Pushover keys are missing": the names in step 10 must be
  exactly `PUSHOVER_USER` and `PUSHOVER_TOKEN`.
- If it says "Pushover rejected the message": one of the keys is wrong. Create
  the secret again with the right key.
- Also check that you are logged in to the Pushover app.

**2. The phone doesn't ring when it is on silent.**
In the Pushover app: **Settings** → under **Alert Settings**, turn on
**Critical Alerts for emergency-priority** (not the one for high-priority). If it
is already on, check that **Critical Alerts** is allowed under the iPhone's
**Settings** → **Notifications** → **Pushover**. Then run **Send test message**
again with the phone on silent.

**3. The Monday "still running" message didn't come.**
Open **Actions** → **Watch for homes**. If it says the workflow is disabled, click
**Enable workflow**. Then click **Run workflow** → **Run workflow**. It should
work again within a few minutes.
If GitHub instead says that Actions, the repository or your account has been
disabled or suspended (GitHub also emails you), GitHub has stopped Boligvagt.
You can appeal at **support.github.com**. Making a new account to start again
is against GitHub's rules, and that account may be closed too. Use the
websites' own apps meanwhile, and tell Simon.

**4. You get "Boligvagt cannot read …" or "… is refusing Boligvagt".**
One of the websites has changed or is blocking. The other sites are still being
watched. Use that site's own app meanwhile. If it lasts more than a couple of days,
ask Claude for help with the prompt below.

**5. Pushover stops after 30 days.**
The free trial has ended. Open the Pushover app and buy it ($4.99 once).

## If you get stuck: prompt for Claude

Copy the text below into Claude and fill in the two fields:

> I use "boligvagt", a small Python program that runs on GitHub Actions in my
> public repo github.com/<your-username>/boligvagt and sends Pushover notifications
> about new rental homes in Copenhagen. Settings are in settings.toml, keys in
> GitHub secrets. I can't code, so please explain briefly and step by step what to
> click in GitHub in the browser.
> Problem: <describe briefly what happens>
> The last lines of the log (Actions → Watch for homes → top run → "Watch"):
> <paste>

## Running Boligvagt for someone else

You can run Boligvagt on your GitHub account for a friend, so they never touch
GitHub. Use a GitHub account only for this (see the warning in Part 2).

1. Your friend follows [START-HERE.md](START-HERE.md) and sends you their
   **Pushover User Key**.
2. You do Part 1 (your own Pushover) and Part 2, but create three secrets in
   step 10:
   - `PUSHOVER_USER`: your friend's User Key. Homes go to them.
   - `PUSHOVER_TOKEN`: the app key you created in step 6.
   - `PUSHOVER_HELPER`: your own User Key. You get the same warnings, the
     welcome, the test and the Monday message as your friend, but not the homes.
3. Run **Send test message** with your friend, so you both know their phone rings
   on silent.

To change their search, edit **settings.toml** as described above. If something
is wrong in it, you both get a message.
