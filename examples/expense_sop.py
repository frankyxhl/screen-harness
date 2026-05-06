start_recording("expense_create_request")

chapter("Create expense request")

step("Open expense system")
caption("Open the company back office and enter the expense system.")
wait_for_user("Open the expense system, then press Enter.")

step("Create request")
caption("Click New Request to open the expense form.")
highlight_region(1240, 88, 180, 64, text="New Request")
wait_for_user("Open the request form, then press Enter.")

step("Fill request details")
caption("Enter amount, expense type, reason, and attachments.")
wait_for_user("Fill the form, then press Enter.")

step("Submit request")
caption("Confirm the details and submit the request.")
highlight_region(1320, 920, 160, 64, text="Submit")
redact_region(300, 180, 360, 80, reason="sample sensitive area", duration=4.0)
wait_for_user("Submit the request, then press Enter.")

stop_recording()
render()
