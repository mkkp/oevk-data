1. Create a function in transformation pipeline to compress exported CSV files using zip. The zip file should be named agter tag and contain all CSV files.
The name synthesis should be: oevk-{RUN_TAG}_export.zip.
Another zip file should be created for duckdb database file named oevk-{RUN_TAG}_database.zip
2. Create a github workflow to run pipeline on every push to main branch or executed by manually. The workflow should:
- Set up Python environment
- Install dependencies
- Run the entire pipeline with a unique RUN_TAG based on the current date (e.g., YYYYMMDD format)
- Create a release and upload the generated zip files. The release name should be {RUN_TAG} and the description should include a summary of changes since the last release.
- Clean the local git repository by removing the generated zip files and any other temporary files created during the pipeline execution.
3. Tag the commit with the same {RUN_TAG}.
3. Update the release section in README.md file related to new workflow.
