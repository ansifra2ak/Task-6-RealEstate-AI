terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
provider "aws" {
  region = var.region
}
variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "ssh_cidr" {
  type        = string
  description = "Your public IPv4 address as a /32, not 0.0.0.0/0."
  validation {
    condition     = can(cidrnetmask(var.ssh_cidr)) && endswith(var.ssh_cidr, "/32")
    error_message = "Supply your own public IPv4 address with /32."
  }
}
variable "key_name" {
  type        = string
  description = "Existing EC2 SSH key pair name in the chosen region."
}
variable "instance_type" {
  type    = string
  default = "t3.large"
}
data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
resource "aws_vpc" "app" {
  cidr_block           = "10.69.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "task6-phase9" }
}
resource "aws_subnet" "app" {
  vpc_id                  = aws_vpc.app.id
  cidr_block              = "10.69.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
}
resource "aws_internet_gateway" "app" {
  vpc_id = aws_vpc.app.id
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.app.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.app.id
  }
}
resource "aws_route_table_association" "app" {
  subnet_id      = aws_subnet.app.id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "app" {
  name_prefix = "task6-phase9-"
  vpc_id      = aws_vpc.app.id
  ingress {
    description = "SSH from owner"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }
  ingress {
    description = "HTTP certificate challenge and HTTPS redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Authenticated HTTPS dashboard"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_instance" "app" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.app.id
  vpc_security_group_ids      = [aws_security_group.app.id]
  associate_public_ip_address = true
  key_name                    = var.key_name
  user_data                   = file("${path.module}/cloud-init.sh")
  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    volume_size           = 40
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  tags = { Name = "task6-phase9" }
}
resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id
}
output "public_ip" {
  value = aws_eip.app.public_ip
}
