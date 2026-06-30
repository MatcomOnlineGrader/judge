# Matcom Online Grader (MOG)

[![Discord](https://img.shields.io/badge/Discord-Join%20our%20community-7289DA?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/ZVYCzPXMGa)

[![](mog/static/mog/images/logo.png)](mog/static/mog/images/logo.png)

## About

Matcom Online Grader (MOG) is a competitive programming platform designed for hosting programming contests and practice sessions. The platform is actively used for ICPC Caribbean Finals and other programming competitions.

🌐 **Live Platform**: [https://matcomgrader.com/](https://matcomgrader.com/)

## Features

- Contest management and hosting
- Real-time submission grading
- User rankings and statistics
- Problem management
- Team registration and management
- Multi-language support for competitive programming
- Caribbean ICPC staff management tools for official competition administration.

## Local Development Setup

### Using Docker (Recommended)

```bash
./updev.sh
```

This will set up the development environment using Docker containers.

#### Apple Silicon (arm64) Macs

The grader image is x86_64-only (it bundles a custom gcc 11.3.0 toolchain), so it
is built and run as `linux/amd64` under emulation. This requires:

- **buildx** — `updev.sh` registers Homebrew's plugin automatically; install it
  with `brew install docker-buildx` if it's missing.
- **Rosetta emulation, not QEMU** — QEMU crashes the compiler. If you use
  [Colima](https://github.com/abiosoft/colima), start it with Rosetta:

  ```bash
  colima start --vz-rosetta --cpu 4 --memory 6
  ```

  Docker Desktop users should enable *Settings → General → Use Rosetta for
  x86/amd64 emulation*.

## Contributing

We welcome contributions! Join our Discord community to discuss features, report bugs, or get help with development.

[![Discord](https://img.shields.io/badge/Discord-Join%20our%20community-7289DA?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/ZVYCzPXMGa)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
