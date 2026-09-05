# Alpha Shop – Gold / Silver / Bronze

Service order in the bot is fixed as: Gold → Silver → Bronze.

- Gold: existing Gold panel, 5,000 Toman/GB
- Silver: new panel at `https://pan.linkesubs.com`, 3,000 Toman/GB
- Bronze: the previous Silver panel, 1,000 Toman/GB
- Free trial: 150 MB per service

Set the new Silver credentials in deployment environment variables:
`SILVER_PANEL_URL_NEW`, `SILVER_PANEL_USERNAME_NEW`, `SILVER_PANEL_PASSWORD_NEW`.
Do not put the real password in Git.

Existing databases are migrated automatically: old `silver` plans become `bronze`, and new Silver plans are created.
