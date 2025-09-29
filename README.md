# Hugging Face GUI Explorer

## About the Project

The Hugging Face GUI Explorer is a desktop application designed to provide a user-friendly interface for searching, exploring, and downloading models from the Hugging Face Hub. It allows users to easily find models, view their details, and download them for local use, all without leaving the application.

This project was built to simplify the process of interacting with the vast collection of models available on the Hugging Face Hub, making it more accessible to developers and researchers.

## Features

*   **Advanced Search:** Search for models with filters for task, library, and more.
*   **Sort and Filter:** Sort results by downloads, likes, or last modified date.
*   **Model Details:** View detailed model information and README files directly in the app.
*   **Model Downloading:** Download models to your local machine with a single click.
*   **Dark Mode:** A sleek, modern dark theme for comfortable viewing.
*   **Responsive UI:** A non-blocking interface that remains responsive during network operations.

## Setup and Installation

To get started with the Hugging Face GUI Explorer, follow these simple steps.

### Prerequisites

*   Python 3.8 or higher
*   pip (Python package installer)

### Installation

1.  **Clone the repository:**
    ```sh
    git clone <repository-url>
    cd hugging-face-gui-explorer
    ```

2.  **Create a virtual environment (recommended):**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    The required Python packages are listed in `requirements.txt`. Install them using pip:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

Once you have completed the setup and installation, you can run the application with the following command from the root directory:

```sh
python -m src.main
```

This will launch the main window of the Hugging Face GUI Explorer, where you can start searching for and exploring models.

## Running Tests

This project uses Python's built-in `unittest` framework for testing. To run the tests, navigate to the root directory of the project and run the following command:

```sh
python -m unittest discover tests
```

This command will automatically discover and run all tests located in the `tests/` directory.

## License

This project is licensed under the **GNU Affero General Public License v3.0**. See the `LICENSE` file for more details.