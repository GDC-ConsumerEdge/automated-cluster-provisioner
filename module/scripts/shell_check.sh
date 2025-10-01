cat ../bootstrap/create-cluster.yaml | yq '.steps[0].script' -r > /tmp/create-cluster.sh
cat ../bootstrap/modify-cluster.yaml | yq '.steps[0].script' -r > /tmp/modify-cluster.sh

shellcheck -S warning /tmp/create-cluster.sh
shellcheck -S warning /tmp/modify-cluster.sh
