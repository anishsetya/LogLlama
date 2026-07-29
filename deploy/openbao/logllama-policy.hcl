path "secret/data/logllama/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "secret/metadata/logllama/*" {
  capabilities = ["read", "list", "delete"]
}
