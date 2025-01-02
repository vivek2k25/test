import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.testng.annotations.Test;

public class CSSSelectionexamples {

        @Test
        public void csseexp() throws InterruptedException {


            // Set up the ChromeDriver
            System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
            WebDriver driver = new ChromeDriver();

            // Navigate to the practice form
            driver.get("https://demoqa.com/automation-practice-form");

            driver.manage().window().maximize();

            // Locate elements using CSS selectors and interact with them

            // First Name
            WebElement firstName = driver.findElement(By.cssSelector("input#firstName"));
            firstName.sendKeys("John");

            // Last Name
            WebElement lastName = driver.findElement(By.cssSelector("input#lastName"));
            lastName.sendKeys("Doe");

            // Email
            WebElement email = driver.findElement(By.cssSelector("input#userEmail"));
            email.sendKeys("john.doe@example.com");

            // Gender
            WebElement genderMale = driver.findElement(By.cssSelector("input#gender-radio-1"));
            genderMale.click();

            // Mobile Number
            WebElement mobile = driver.findElement(By.cssSelector("input#userNumber"));
            mobile.sendKeys("1234567890");

            // Date of Birth
            WebElement dateOfBirth = driver.findElement(By.cssSelector("input#dateOfBirthInput"));
            dateOfBirth.click();
            WebElement monthSelect = driver.findElement(By.cssSelector(".react-datepicker__month-select"));
            monthSelect.click();
            WebElement monthOption = driver.findElement(By.cssSelector(".react-datepicker__month-select option[value='4']"));
            monthOption.click();
            WebElement yearSelect = driver.findElement(By.cssSelector(".react-datepicker__year-select"));
            yearSelect.click();
            WebElement yearOption = driver.findElement(By.cssSelector(".react-datepicker__year-select option[value='1990']"));
            yearOption.click();
            WebElement daySelect = driver.findElement(By.cssSelector(".react-datepicker__day--020"));
            daySelect.click();

            // Subjects
            WebElement subjects = driver.findElement(By.cssSelector("input#subjectsInput"));
            subjects.sendKeys("Maths");

            // Hobbies
            WebElement hobbyReading = driver.findElement(By.cssSelector("input#hobbies-checkbox-2"));
            hobbyReading.click();

            // Submit Button

            Thread.sleep(1000);
            WebElement submitButton = driver.findElement(By.cssSelector("button#submit"));
            submitButton.click();

            // Close the browser
//            driver.quit();
        }
    }

