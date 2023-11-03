# assignmentbot
GDSC CU Assignment Bot
## Description
This is a telegram bot for sending daily reminders to a group chat of an assignment set by the admin. Bot must also be an admin to work properly.

## How it works.
1. Bot must be added as an admin to the group where it will be sending reminders to.
2. An assignment is created by using the command 'addassignmennt' on the group. This command should be registered with botfather to see it in the menu. This command can only be used by admins in the chat.
3. Bot replies with format for creating a new assignment. See format [below](https://github.com/dsccovenantuniversity/assignmentbot/new/main?readme=1#format-for-creating-assignments). Bot message must be *replied to* (that is rght in the message and select reply) for the assignment to be saved.
4. Command 'getassignments' is used to list all assignments created in that chat group. Command restricted to admins. List returned would contain inline buttons for editing, deletion and viewing. The list is returned in the form of replies to the message that sends the command.
5. Assignment reminders sent everyday by 12pm

## Deployment.
Deployment works easily on any platform that allows python deployments. Most platforms run  the 
pip install requirements.txt 
command automatically. If not that must be done manually.

It's coded to run off a firebase real-time database. Head over to firebase.io and create a new project. You can learn more here [Firebase Docs](firebase.google.com/docs/database)
Once you have gotten your database up. Create some access rules for 'assignments, like so

```JSON
{
"assignments" : {
    ".read" : true,
    ".write" : true,
}
```
Simply add that snippet under the default "rules" that you'll see there.
If you don't do this you'll get access errors. You're essentially giving permission for everything under assignments to be accessed by those with the right credentials.

Once the database is setup, navigate to your project settings and go to service accounts and setup a new private key. Copy these details and set them in your deployment provider as ENV variables.

### Format for Creating Assignments
Please adhere to this format strictly in creating assignments.

*Course Code*: __course code__

*Title*: __assignment title__

*Deadline*: dd/mm/yy
*Description*: __assignment description__
