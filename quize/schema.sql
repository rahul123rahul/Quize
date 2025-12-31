CREATE TABLE IF NOT EXISTS Users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100),
    role ENUM('Admin', 'Coordinator', 'Student')
);

CREATE TABLE IF NOT EXISTS Quizzes (
    quiz_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(200),
    marks INT
);

CREATE TABLE IF NOT EXISTS Quiz_Attempts (
    attempt_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    total_score DECIMAL(5,2),
    status VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS Quiz_Responses (
    response_id INT PRIMARY KEY AUTO_INCREMENT,
    attempt_id INT,
    question_id INT,
    selected_option VARCHAR(1),
    is_attempted BOOLEAN
);

CREATE TABLE IF NOT EXISTS Questions (
    question_id INT PRIMARY KEY AUTO_INCREMENT,
    question_text TEXT,
    correct_option VARCHAR(1),
    marks INT
);