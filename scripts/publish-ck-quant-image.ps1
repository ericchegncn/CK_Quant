param(
    [string]$DockerHubNamespace = "ericchenghz",
    [string]$Tag = "stable",
    [switch]$AlsoLatest
)

$ErrorActionPreference = "Stop"
$image = "$DockerHubNamespace/ck-quant:$Tag"

docker build --tag $image .
docker run --rm $image --version
docker push $image

if ($AlsoLatest) {
    $latest = "$DockerHubNamespace/ck-quant:latest"
    docker tag $image $latest
    docker push $latest
}

Write-Host "Published $image"
