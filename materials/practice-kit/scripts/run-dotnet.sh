#!/bin/sh
# Исходники подключены только для чтения; все obj/bin остаются в одноразовом контейнере.
set -eu
project_dir=$(mktemp -d /tmp/course-dotnet.XXXXXX)
cp -R /source/. "$project_dir/"
cd "$project_dir"
dotnet --version
dotnet build Quantity/Quantity.csproj --configuration Release
dotnet run --project Quantity/Quantity.csproj --configuration Release --no-build
dotnet build reference/Reference.csproj --configuration Release
dotnet run --project reference/Reference.csproj --configuration Release --no-build
if [ "${RUN_API_CLIENT:-0}" = "1" ]; then
    dotnet run --project Client/Client.csproj --configuration Release
fi
