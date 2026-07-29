# Local persistent profile. Production must enable TLS and use a multi-node Raft cluster.
ui = true

api_addr = "http://127.0.0.1:8200"
cluster_addr = "http://openbao:8201"

storage "raft" {
  path = "/openbao/file"
  node_id = "logllama-openbao-local"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_disable = true
}

audit "file" "stdout" {
  description = "OpenBao API audit trail"
  options {
    file_path = "stdout"
    log_raw = "false"
  }
}
