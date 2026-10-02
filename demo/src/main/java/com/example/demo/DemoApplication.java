package com.example.demo;

import org.mybatis.spring.annotation.MapperScan;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;
import org.springframework.web.reactive.function.client.WebClient;

@SpringBootApplication
@MapperScan({"com.example.demo.auth.mapper", "com.example.demo.community.mapper"})
public class DemoApplication {

	private static final Logger log = LoggerFactory.getLogger(DemoApplication.class);

	public static void main(String[] args) {
		SpringApplication.run(DemoApplication.class, args);
	}

	@Bean
	ApplicationRunner logDataSourceUrl(Environment env) {
		return args -> log.info(
				"[bitdance] spring.profiles.active={} jdbc.url={}",
				String.join(",", env.getActiveProfiles()),
				env.getProperty("spring.datasource.url"));
	}

	// Provide a WebClient.Builder bean so components that require it can be autowired
	@Bean
	public WebClient.Builder webClientBuilder() {
		return WebClient.builder();
	}

}
