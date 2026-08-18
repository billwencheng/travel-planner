cd deployment/terraform/single-project
export TF_VAR_project_id=super-billwencheng-test001
terraform import google_firestore_database.default projects/super-billwencheng-test001/databases/\(default\) || true
terraform import google_service_account.app_sa projects/super-billwencheng-test001/serviceAccounts/travel-planner-app@super-billwencheng-test001.iam.gserviceaccount.com || true
terraform import google_secret_manager_secret.api_keys projects/super-billwencheng-test001/secrets/travel-planner-api-keys || true
terraform import google_storage_bucket.logs_data_bucket super-billwencheng-test001-travel-planner-logs || true
terraform import google_bigquery_table.genai_logs_table projects/super-billwencheng-test001/datasets/travel_planner_telemetry/tables/gen_ai_client_inference_operation_details || true
terraform apply -auto-approve
