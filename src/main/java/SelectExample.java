import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.support.ui.Select;
import org.testng.annotations.Test;

import java.util.List;

public class SelectExample {

    @Test
    public void selectexamples() throws InterruptedException {


        // Set up the ChromeDriver
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        WebDriver driver = new ChromeDriver();

        // Navigate to the practice form
        driver.get("https://demoqa.com/select-menu");

        //  Dimension targetSize = new Dimension(1024, 1024);
        //  driver.manage().window().setSize(targetSize);

        driver.manage().window().maximize();

        Thread.sleep(1000);

       Select sec = new Select( driver.findElement(By.xpath("//*[@id='oldSelectMenu']")));

        sec.selectByIndex(4);

        System.out.println(" It will select the item of idex 4 ");


        Thread.sleep(2000);

        // now select the value using selectbyValue

        Select sec2 = new Select( driver.findElement(By.xpath("//*[@id='oldSelectMenu']")));

        sec2.selectByValue("6");

        System.out.println(" It will select White ");

        Thread.sleep(2000);

        Select sec3 = new Select(driver.findElement(By.xpath("//*[@id='oldSelectMenu']")));
        sec.selectByVisibleText("Indigo");
        System.out.println(" Indigo is get selected");



        Select sec4 = new Select(driver.findElement(By.xpath("//*[@id='oldSelectMenu']")));

        List<WebElement> options = sec4.getOptions();

        for(WebElement abc :options)
        {
            System.out.println("Print all the element of list == " + abc.getText());
        }



        sec.selectByVisibleText("Indigo");
        System.out.println(" Indigo is get selected");

        WebElement firstselect = sec3.getFirstSelectedOption();

        System.out.println("First selected item = " + firstselect.getText());



    }
}

